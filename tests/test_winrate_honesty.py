"""
Win rates must be measured or absent — never invented.

`StatsScraper` shipped a hand-written table of ~170 ARAM win rates, and
derived the other three modes from it by arithmetic:

    RANKED    = ARAM - 1.5
    ARENA     = ARAM + 2.0
    QUICKPLAY = ARAM - 0.5

`get_winrate()` then fell back to that table, and failing that to a flat
`50.0`, so every champion always had a plausible percentage. The champion
tile displayed it and the tooltip credited it to **Lolalytics**. None of it
was measured, and `fetch_live` defaults to False so the scraper never ran.

These tests pin the honest behaviour: no data means no number.
"""
import unittest

from services.stats_scraper import StatsScraper


def scraper(mode="ARAM", live=None):
    s = StatsScraper(mode=mode, fetch_live=False)
    if live is not None:
        s.live_winrates[s.mode] = live
    return s


class NoInventedNumbersTests(unittest.TestCase):
    def test_an_unfetched_winrate_is_none_not_fifty(self):
        self.assertIsNone(scraper().get_winrate("Ahri"))

    def test_an_unknown_champion_is_none(self):
        self.assertIsNone(scraper().get_winrate("Notachampion"))

    def test_a_scraped_winrate_is_returned(self):
        s = scraper(live={"ahri": 53.4})
        self.assertEqual(s.get_winrate("Ahri"), 53.4)

    def test_name_cleaning_still_works(self):
        s = scraper(live={"leesin": 51.0, "chogath": 52.0})
        self.assertEqual(s.get_winrate("Lee Sin"), 51.0)
        self.assertEqual(s.get_winrate("Cho'Gath"), 52.0)

    def test_the_source_is_empty_when_nothing_was_scraped(self):
        self.assertEqual(scraper().winrate_source(), "")
        self.assertFalse(scraper().has_live_winrates())

    def test_the_source_is_named_when_something_was(self):
        s = scraper(live={"ahri": 53.4})
        self.assertEqual(s.winrate_source(), "lolalytics")
        self.assertTrue(s.has_live_winrates())


class DerivedTablesTests(unittest.TestCase):
    def test_modes_no_longer_differ_by_arithmetic(self):
        """
        RANKED was ARAM minus 1.5 for every champion. Two modes cannot
        legitimately differ by a constant.
        """
        from services import stats_scraper as ss

        self.assertIs(ss.BASELINE_RANKED_WINRATES, ss.BASELINE_ARAM_WINRATES)
        self.assertIs(ss.BASELINE_ARENA_WINRATES, ss.BASELINE_ARAM_WINRATES)

    def test_the_baseline_is_still_available_for_internal_ordering(self):
        """It may break a tie inside automation. It may not reach the screen."""
        hint = scraper().get_ordering_hint("Ahri")
        self.assertIsInstance(hint, float)
        self.assertGreater(hint, 0)

    def test_the_ordering_hint_prefers_real_data(self):
        s = scraper(live={"ahri": 60.0})
        self.assertEqual(s.get_ordering_hint("Ahri"), 60.0)


if __name__ == "__main__":
    unittest.main()

