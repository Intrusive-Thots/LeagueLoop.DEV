import os
import tempfile
import unittest
from database.db_manager import DatabaseManager


class TestDatabaseManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_leagueloop.db")
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            os.rmdir(self.temp_dir)
        except OSError:
            pass

    def test_settings_persistence(self):
        self.db.set_setting("auto_accept", True)
        self.db.set_setting("priority_list", ["Nautilus", "Xerath"])

        self.assertTrue(self.db.get_setting("auto_accept"))
        self.assertEqual(self.db.get_setting("priority_list"), ["Nautilus", "Xerath"])
        self.assertIsNone(self.db.get_setting("non_existent_key"))

    def test_history_logging(self):
        self.db.log_history("Nautilus", "UTILITY", "PICK")
        history = self.db.get_recent_history(limit=10)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["champion_name"], "Nautilus")
        self.assertEqual(history[0]["action"], "PICK")


if __name__ == "__main__":
    unittest.main()
