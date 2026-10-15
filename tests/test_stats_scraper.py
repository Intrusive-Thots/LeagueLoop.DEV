"""
Unit tests for StatsScraper in src/services/stats_scraper.py
"""
import time
import unittest
from unittest.mock import MagicMock, patch

import requests

from services.stats_scraper import (
    BASELINE_ARAM_WINRATES,
    BASELINE_ARENA_WINRATES,
    BASELINE_QUICKPLAY_WINRATES,
    BASELINE_RANKED_WINRATES,
    StatsScraper,
)


class BaseScraperTest(unittest.TestCase):
    def setUp(self):
        self.scrapers = []

    def create_scraper(self, mode="ARAM", fetch_live=False):
        scraper = StatsScraper(mode=mode, fetch_live=fetch_live)
        self.scrapers.append(scraper)
        return scraper

    def tearDown(self):
        for scraper in self.scrapers:
            try:
                scraper._executor.shutdown(wait=False)
            except Exception:
                pass


class TestStatsScraperInitializationAndModes(BaseScraperTest):
    def test_init_defaults(self):
        scraper = self.create_scraper()
        self.assertEqual(scraper.mode, "ARAM")
        self.assertFalse(scraper.fetch_live)
        self.assertEqual(scraper.win_rates, BASELINE_ARAM_WINRATES)
        self.assertEqual(scraper.live_winrates, {})

    def test_set_mode_aram(self):
        scraper = self.create_scraper(mode="Ranked")
        scraper.set_mode("ARAM")
        self.assertEqual(scraper.mode, "ARAM")
        self.assertEqual(scraper.win_rates, BASELINE_ARAM_WINRATES)

    def test_set_mode_arena(self):
        scraper = self.create_scraper()
        scraper.set_mode("Arena")
        self.assertEqual(scraper.mode, "Arena")
        self.assertEqual(scraper.win_rates, BASELINE_ARENA_WINRATES)

    def test_set_mode_quickplay_and_fun_modes(self):
        scraper = self.create_scraper()
        for mode_name in ["Quickplay", "Nexus Blitz", "One For All", "Ultimate Spellbook"]:
            scraper.set_mode(mode_name)
            self.assertEqual(scraper.mode, mode_name)
            self.assertEqual(scraper.win_rates, BASELINE_QUICKPLAY_WINRATES)

    def test_set_mode_ranked(self):
        scraper = self.create_scraper()
        scraper.set_mode("Ranked Solo/Duo")
        self.assertEqual(scraper.mode, "Ranked Solo/Duo")
        self.assertEqual(scraper.win_rates, BASELINE_RANKED_WINRATES)

    def test_set_mode_by_queue_id_known(self):
        scraper = self.create_scraper()
        scraper.set_mode_by_queue_id(420)
        self.assertEqual(scraper.win_rates, dict(BASELINE_RANKED_WINRATES))
        self.assertEqual(scraper.mode, "Ranked Solo/Duo")

        scraper.set_mode_by_queue_id(1700)
        self.assertEqual(scraper.win_rates, dict(BASELINE_ARENA_WINRATES))
        self.assertEqual(scraper.mode, "Arena")

    def test_set_mode_by_queue_id_unknown(self):
        scraper = self.create_scraper(mode="ARAM")
        scraper.set_mode_by_queue_id(99999)
        self.assertEqual(scraper.win_rates, dict(BASELINE_ARAM_WINRATES))

    def test_set_mode_by_queue_id_import_fallback(self):
        scraper = self.create_scraper()
        with patch.dict("sys.modules", {"services.queue_manager": None}):
            scraper.set_mode_by_queue_id(450)
            self.assertEqual(scraper.mode, "ARAM")


class TestStatsScraperWinrateLookups(BaseScraperTest):
    def test_get_winrate_without_live_returns_none(self):
        scraper = self.create_scraper(mode="ARAM", fetch_live=False)
        self.assertIsNone(scraper.get_winrate("Ahri"))
        self.assertIsNone(scraper.get_winrate("UnknownChamp"))

    def test_get_winrate_with_live_data(self):
        scraper = self.create_scraper(mode="ARAM", fetch_live=False)
        scraper.live_winrates["ARAM"] = {
            "ahri": 52.5,
            "chogath": 54.1,
            "leesin": 49.0,
        }
        self.assertEqual(scraper.get_winrate("Ahri"), 52.5)
        self.assertEqual(scraper.get_winrate("Cho'Gath"), 54.1)
        self.assertEqual(scraper.get_winrate("Lee Sin"), 49.0)
        self.assertIsNone(scraper.get_winrate("Garen"))

    def test_get_ordering_hint_prefers_live_then_baseline_then_default(self):
        scraper = self.create_scraper(mode="ARAM", fetch_live=False)
        scraper.live_winrates["ARAM"] = {"ahri": 60.0}

        # 1. Live winrate
        self.assertEqual(scraper.get_ordering_hint("Ahri"), 60.0)

        # 2. Baseline lookup (Ahri is in BASELINE_ARAM_WINRATES as 52.1)
        # For Garen, not in live_winrates, so uses baseline
        self.assertEqual(
            scraper.get_ordering_hint("Garen"),
            BASELINE_ARAM_WINRATES["garen"]
        )

        # 3. Completely unknown champion falls back to 50.0
        self.assertEqual(scraper.get_ordering_hint("NonExistentChampion123"), 50.0)

    def test_winrate_source_and_status_properties(self):
        scraper = self.create_scraper(mode="ARAM", fetch_live=False)

        # Offline / no live data state
        self.assertEqual(scraper.winrate_source(), "")
        self.assertFalse(scraper.has_live_winrates())
        self.assertTrue(scraper.is_offline)

        # Online / live data present state
        scraper.live_winrates["ARAM"] = {"ahri": 52.5}
        self.assertEqual(scraper.winrate_source(), "lolalytics")
        self.assertTrue(scraper.has_live_winrates())
        self.assertFalse(scraper.is_offline)


class TestStatsScraperBackgroundFetching(BaseScraperTest):
    def test_fetch_live_data_background_disabled(self):
        scraper = self.create_scraper(mode="ARAM", fetch_live=False)
        with patch.object(scraper._executor, "submit") as mock_submit:
            scraper._fetch_live_data_background("ARAM")
            mock_submit.assert_not_called()

    def test_fetch_live_data_background_cache_hit(self):
        scraper = self.create_scraper(mode="ARAM", fetch_live=True)
        scraper.live_winrates["ARAM"] = {"ahri": 52.5}
        scraper._cache_timestamps["ARAM"] = time.time()

        with patch.object(scraper._executor, "submit") as mock_submit:
            scraper._fetch_live_data_background("ARAM")
            mock_submit.assert_not_called()

    @patch("services.stats_scraper._HAS_BS4", False)
    def test_fetch_live_data_background_no_bs4(self):
        scraper = self.create_scraper(mode="ARAM", fetch_live=True)
        with patch.object(scraper._executor, "submit") as mock_submit:
            scraper._fetch_live_data_background("ARAM")
            mock_submit.assert_not_called()

    @patch("services.stats_scraper._HAS_BS4", True)
    def test_fetch_live_data_background_submits_task(self):
        scraper = self.create_scraper(mode="ARAM", fetch_live=True)
        with patch.object(scraper._executor, "submit") as mock_submit:
            scraper._fetch_live_data_background("ARAM")
            mock_submit.assert_called_once_with(scraper._scrape_winrates, "ARAM")


class TestStatsScraperScrapeWinrates(BaseScraperTest):
    def setUp(self):
        super().setUp()
        self.mock_session = MagicMock()
        self.patcher = patch("services.stats_scraper.get_shared_session", return_value=self.mock_session)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        super().tearDown()

    def test_scrape_winrates_http_error(self):
        mock_get = self.mock_session.get
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        scraper = self.create_scraper(mode="ARAM", fetch_live=False)
        scraper._scrape_winrates("ARAM")
        self.assertNotIn("ARAM", scraper.live_winrates)

    def test_scrape_winrates_network_exception(self):
        mock_get = self.mock_session.get
        mock_get.side_effect = requests.RequestException("Connection error")

        scraper = self.create_scraper(mode="ARAM", fetch_live=False)
        scraper._scrape_winrates("ARAM")
        self.assertNotIn("ARAM", scraper.live_winrates)

    def test_scrape_winrates_general_exception(self):
        mock_get = self.mock_session.get
        mock_get.side_effect = Exception("Unexpected error")

        scraper = self.create_scraper(mode="ARAM", fetch_live=False)
        scraper._scrape_winrates("ARAM")
        self.assertNotIn("ARAM", scraper.live_winrates)

    def test_scrape_winrates_successful_parsing(self):
        mock_get = self.mock_session.get
        # Build a synthetic HTML table with 25 champion rows
        rows_html = ""
        champions = [f"champ{i}" for i in range(25)]
        for idx, champ in enumerate(champions):
            wr = 50.0 + idx * 0.5
            rows_html += f"<tr><td>{champ}</td><td>{wr:.1f}%</td><td>1000</td></tr>"

        html_content = f"<html><body><table>{rows_html}</table></body></html>"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html_content
        mock_get.return_value = mock_resp

        scraper = self.create_scraper(mode="ARAM", fetch_live=False)

        # Test ARAM URL routing
        scraper._scrape_winrates("ARAM")
        mock_get.assert_called_with(
            "https://lolalytics.com/lol/tierlist/aram/",
            timeout=12,
            headers=unittest.mock.ANY,
        )
        self.assertIn("ARAM", scraper.live_winrates)
        self.assertEqual(len(scraper.live_winrates["ARAM"]), 25)
        self.assertEqual(scraper.live_winrates["ARAM"]["champ0"], 50.0)

        # Test Arena URL routing
        mock_get.reset_mock()
        scraper._scrape_winrates("Arena")
        mock_get.assert_called_with(
            "https://lolalytics.com/arena/",
            timeout=12,
            headers=unittest.mock.ANY,
        )

        # Test Ranked/Other URL routing
        mock_get.reset_mock()
        scraper._scrape_winrates("Ranked Solo/Duo")
        mock_get.assert_called_with(
            "https://lolalytics.com/lol/tierlist/",
            timeout=12,
            headers=unittest.mock.ANY,
        )

    def test_scrape_winrates_too_few_results_discarded(self):
        mock_get = self.mock_session.get
        # Build synthetic HTML with only 5 champions (< 20 threshold)
        rows_html = ""
        for i in range(5):
            rows_html += f"<tr><td>champ{i}</td><td>52.0%</td><td>100</td></tr>"

        html_content = f"<html><body><table>{rows_html}</table></body></html>"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html_content
        mock_get.return_value = mock_resp

        scraper = self.create_scraper(mode="ARAM", fetch_live=False)
        scraper._scrape_winrates("ARAM")
        self.assertNotIn("ARAM", scraper.live_winrates)


if __name__ == "__main__":
    unittest.main()
