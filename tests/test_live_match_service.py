import unittest
from unittest.mock import MagicMock, patch

from services.live_match_service import LiveMatchService, get_live_match_service


class TestLiveMatchService(unittest.TestCase):

    def setUp(self):
        self.service = LiveMatchService()

    def test_singleton_accessor(self):
        inst1 = get_live_match_service()
        inst2 = get_live_match_service()
        self.assertIs(inst1, inst2)

    def test_fetch_all_game_data_failure_returns_none(self):
        with patch.object(self.service.session, "get", side_effect=Exception("Connection refused")):
            data = self.service.fetch_all_game_data()
            self.assertIsNone(data)
            self.assertFalse(self.service.is_active)

    def test_get_match_summary_parsing(self):
        self.service._last_data = {
            "gameData": {"gameTime": 120.5},
            "allPlayers": [
                {
                    "summonerName": "Player1",
                    "championName": "Aatrox",
                    "team": "ORDER",
                    "scores": {"kills": 3, "deaths": 1, "assists": 2, "creepScore": 85},
                    "items": [{"price": 1100}, {"price": 1300}],
                },
                {
                    "summonerName": "Enemy1",
                    "championName": "Darius",
                    "team": "CHAOS",
                    "scores": {"kills": 1, "deaths": 3, "assists": 0, "creepScore": 70},
                    "items": [{"price": 1100}],
                },
            ],
        }
        self.service.is_active = True

        summary = self.service.get_match_summary()
        self.assertTrue(summary["in_game"])
        self.assertEqual(summary["blue_kills"], 3)
        self.assertEqual(summary["red_kills"], 1)
        self.assertEqual(summary["blue_gold"], 2400)
        self.assertEqual(summary["red_gold"], 1100)
        self.assertEqual(summary["gold_diff"], 1300)
        self.assertEqual(len(summary["blue_players"]), 1)
        self.assertEqual(len(summary["red_players"]), 1)


if __name__ == "__main__":
    unittest.main()
