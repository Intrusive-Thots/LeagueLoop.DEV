import unittest
from unittest.mock import patch, MagicMock

from services.stats_scraper import StatsScraper

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

if __name__ == '__main__':
    unittest.main()
