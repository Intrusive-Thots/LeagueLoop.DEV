import unittest
import os
import json
from unittest.mock import patch, mock_open
from services.asset_manager import ConfigManager, DEFAULT_CONFIG, USER_CONFIG_FILE as CONFIG_FILE

class TestConfigManager(unittest.TestCase):
    def test_load_default_config(self):
        with patch('os.path.exists', return_value=False):
            config = ConfigManager()
            self.assertEqual(config.cfg, DEFAULT_CONFIG)

    def test_load_existing_config(self):
        test_config = DEFAULT_CONFIG.copy()
        test_config["auto_accept"] = True

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(test_config))):
            config = ConfigManager()
            self.assertEqual(config.get("auto_accept"), True)
            self.assertEqual(config.get("auto_requeue"), False)

    def test_load_corrupted_config(self):
        corrupted_json = "{bad_json: true,"

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=corrupted_json)), \
             patch('services.asset_manager.Logger.error') as mock_logger:
            config = ConfigManager()

            # Should fall back to default config without throwing an exception
            self.assertEqual(config.cfg, DEFAULT_CONFIG)

            # Check if error was logged
            mock_logger.assert_called_once()
            args, _ = mock_logger.call_args
            self.assertEqual(args[0], "asset_manager.py")
            self.assertTrue("Handled exception: JSONDecodeError" in args[1])

    def test_set_and_save(self):
        with patch('os.path.exists', return_value=False), \
             patch('builtins.open', mock_open()) as mocked_file:
            config = ConfigManager()
            config.set("auto_accept", True)
            self.assertEqual(config.get("auto_accept"), True)

            mocked_file.assert_called_with(CONFIG_FILE + ".tmp", "w", encoding="utf-8")
            # We can't easily assert the exact JSON written because of the formatting,
            # but we can check if it was called.

    def test_set_batch_and_save(self):
        with patch('os.path.exists', return_value=False), \
             patch('builtins.open', mock_open()) as mocked_file:
            config = ConfigManager()
            updates = {"auto_accept": True, "auto_requeue": True}
            config.set_batch(updates)

            self.assertEqual(config.get("auto_accept"), True)
            self.assertEqual(config.get("auto_requeue"), True)
            mocked_file.assert_called_with(CONFIG_FILE + ".tmp", "w", encoding="utf-8")

if __name__ == '__main__':
    unittest.main()
