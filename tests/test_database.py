import os
import tempfile
import unittest

from services.database import DatabaseService


class TestDatabaseService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_leagueloop.db")
        self.db = DatabaseService(db_path=self.db_path)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_init_creates_tables(self):
        self.assertTrue(os.path.exists(self.db_path))
        matches = self.db.get_recent_matches()
        self.assertEqual(matches, [])

    def test_record_and_get_match(self):
        match_data = {
            "game_id": 123456789,
            "champion_id": 266,
            "champion_name": "Aatrox",
            "role": "TOP",
            "win": True,
            "kills": 8,
            "deaths": 2,
            "assists": 10,
            "duration_s": 1800,
            "queue_id": 420,
        }
        success = self.db.record_match(match_data)
        self.assertTrue(success)

        retrieved = self.db.get_match(123456789)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["champion_name"], "Aatrox")
        self.assertEqual(retrieved["win"], 1)
        self.assertEqual(retrieved["kills"], 8)
        self.assertEqual(retrieved["deaths"], 2)

    def test_record_match_invalid(self):
        # Missing game_id or champion_id
        self.assertFalse(self.db.record_match({"champion_id": 266}))
        self.assertFalse(self.db.record_match({"game_id": 12345}))

    def test_champion_stats_calculation(self):
        # Insert 3 games: 2 wins, 1 loss
        self.db.record_match({
            "game_id": 1,
            "champion_id": 103,
            "champion_name": "Ahri",
            "win": True,
            "kills": 10,
            "deaths": 2,
            "assists": 5,
        })
        self.db.record_match({
            "game_id": 2,
            "champion_id": 103,
            "champion_name": "Ahri",
            "win": False,
            "kills": 2,
            "deaths": 6,
            "assists": 4,
        })
        self.db.record_match({
            "game_id": 3,
            "champion_id": 103,
            "champion_name": "Ahri",
            "win": True,
            "kills": 6,
            "deaths": 1,
            "assists": 9,
        })
        # Another champion
        self.db.record_match({
            "game_id": 4,
            "champion_id": 266,
            "champion_name": "Aatrox",
            "win": True,
            "kills": 5,
            "deaths": 5,
            "assists": 5,
        })

        stats_ahri = self.db.get_champion_stats(champion_id=103)
        self.assertEqual(stats_ahri["games"], 3)
        self.assertEqual(stats_ahri["wins"], 2)
        self.assertEqual(stats_ahri["losses"], 1)
        self.assertAlmostEqual(stats_ahri["win_rate_pct"], 66.67, places=2)

        stats_overall = self.db.get_champion_stats()
        self.assertEqual(stats_overall["games"], 4)
        self.assertEqual(stats_overall["wins"], 3)
        self.assertAlmostEqual(stats_overall["win_rate_pct"], 75.0, places=2)

    def test_telemetry_snapshot_persistence(self):
        snap = {
            "phase": "InProgress",
            "latency_avg_ms": 12.5,
            "latency_p95_ms": 28.0,
            "ws_events_total": 450,
        }
        res = self.db.record_telemetry_snapshot(snap)
        self.assertTrue(res)

        recent = self.db.get_recent_telemetry(limit=10)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["phase"], "InProgress")
        self.assertEqual(recent[0]["latency_avg_ms"], 12.5)


if __name__ == "__main__":
    unittest.main()
