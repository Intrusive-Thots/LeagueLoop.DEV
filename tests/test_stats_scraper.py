import unittest
from unittest.mock import patch, MagicMock
import time

from services.stats_scraper import StatsScraper, BASELINE_ARAM_WINRATES, BASELINE_ARENA_WINRATES, BASELINE_RANKED_WINRATES, BASELINE_QUICKPLAY_WINRATES

class TestStatsScraper(unittest.TestCase):

    def setUp(self):
        self.scraper = StatsScraper(fetch_live=False)

    def test_get_winrate(self):
        # Disable background fetch for clean state
        scraper = StatsScraper(fetch_live=False)

        # Test normal baseline retrieval
        self.assertEqual(scraper.get_winrate("aatrox"), 49.5)
        self.assertEqual(scraper.get_winrate("ahri"), 52.1)

        # Test string normalization (capitalization, spaces, punctuation)
        self.assertEqual(scraper.get_winrate("Aatrox"), 49.5)
        self.assertEqual(scraper.get_winrate("Kog'Maw"), 54.0)
        self.assertEqual(scraper.get_winrate("Lee Sin"), 49.0)
        self.assertEqual(scraper.get_winrate(" Dr. Mundo "), 53.5)

        # Test fallbacks (baseline is 50.0)
        self.assertEqual(scraper.get_winrate("UnknownChamp"), 50.0)
        self.assertEqual(scraper.get_winrate(""), 50.0)

        # Test with custom fetched data
        scraper.win_rates["testchamp"] = 60.5
        self.assertEqual(scraper.get_winrate("Test Champ"), 60.5)

    def test_set_mode(self):
        scraper = StatsScraper(mode="ARAM", fetch_live=False)
        self.assertEqual(scraper.win_rates, BASELINE_ARAM_WINRATES)

        scraper.set_mode("Arena 2v2v2v2")
        self.assertEqual(scraper.win_rates, BASELINE_ARENA_WINRATES)

        scraper.set_mode("Quickplay Mode")
        self.assertEqual(scraper.win_rates, BASELINE_QUICKPLAY_WINRATES)

        scraper.set_mode("Ranked Solo/Duo")
        self.assertEqual(scraper.win_rates, BASELINE_RANKED_WINRATES)

    def test_set_mode_by_queue_id(self):
        scraper = StatsScraper(fetch_live=False)
        
        # Test ARAM queue 450
        scraper.set_mode_by_queue_id(450)
        self.assertEqual(scraper.mode, "ARAM")

        # Test Arena queue 1700
        scraper.set_mode_by_queue_id(1700)
        self.assertEqual(scraper.mode, "Arena")

        # Test Ranked queue 420
        scraper.set_mode_by_queue_id(420)
        self.assertEqual(scraper.mode, "Ranked Solo/Duo")

        # Test Quickplay queue 490
        scraper.set_mode_by_queue_id(490)
        self.assertEqual(scraper.mode, "Quickplay")

        # Test unknown queue ID fallback
        scraper.set_mode_by_queue_id(9999)
        self.assertIsNotNone(scraper.win_rates)

    def test_is_offline_and_live_data(self):
        scraper = StatsScraper(mode="ARAM", fetch_live=False)
        self.assertTrue(scraper.is_offline)

        scraper.live_winrates["ARAM"] = {"aatrox": 55.0}
        self.assertFalse(scraper.is_offline)
        self.assertEqual(scraper.get_winrate("Aatrox"), 55.0)

    @patch("requests.get")
    def test_scrape_winrates_success(self, mock_get):
        html_content = """
        <html>
            <body>
                <table>
                    <tr><td>Aatrox</td><td>56.2%</td><td>1000</td></tr>
                    <tr><td>Ahri</td><td>54.0%</td><td>1000</td></tr>
                </table>
            </body>
        </html>
        """
        # Create 20+ rows so scrape threshold (>20) passes
        rows = "".join([f"<tr><td>Champ{i}</td><td>{50+i*0.1}%</td><td>100</td></tr>" for i in range(25)])
        html_content = f"<html><body><table>{rows}</table></body></html>"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html_content
        mock_get.return_value = mock_resp

        scraper = StatsScraper(mode="ARAM", fetch_live=False)
        scraper._scrape_winrates("ARAM")
        self.assertIn("ARAM", scraper.live_winrates)
        self.assertIn("champ0", scraper.live_winrates["ARAM"])
        self.assertEqual(scraper.live_winrates["ARAM"]["champ0"], 50.0)

    @patch("requests.get")
    def test_scrape_winrates_failures(self, mock_get):
        scraper = StatsScraper(mode="Ranked", fetch_live=False)
        
        # Test HTTP error status
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp
        scraper._scrape_winrates("Ranked")
        self.assertNotIn("Ranked", scraper.live_winrates)

        # Test request exception
        mock_get.side_effect = Exception("Network connection timeout")
        scraper._scrape_winrates("Ranked")
        self.assertNotIn("Ranked", scraper.live_winrates)

if __name__ == '__main__':
    unittest.main()

