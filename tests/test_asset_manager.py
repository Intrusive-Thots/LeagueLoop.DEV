import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
import json

from services.asset_manager import AssetManager

SAMPLE_CHAMP_DATA = {
    "data": {
        "Aatrox": {"id": "Aatrox", "key": "266", "name": "Aatrox", "tags": ["Fighter"]},
        "Ahri": {"id": "Ahri", "key": "103", "name": "Ahri", "tags": ["Mage"]}
    }
}

class TestAssetManager(unittest.TestCase):
    def setUp(self):
        self.assets = AssetManager()

    def test_init(self):
        self.assertEqual(self.assets.champ_data, {})
        self.assertEqual(self.assets.id_to_key, {})
        self.assertEqual(self.assets.name_to_id, {})

    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_load_champion_data_cache_miss(self, mock_exists, mock_makedirs):
        """When cache file doesn't exist, download from DDragon and populate maps."""
        # First call: cache file doesn't exist -> download
        # Second call: file now exists for reading
        mock_exists.side_effect = [False]

        # Mock the session.get() on the instance
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_CHAMP_DATA
        self.assets.session = MagicMock()
        self.assets.session.get.return_value = mock_response

        self.assets.ddragon_ver = "14.4.1"

        # Mock file write + read to return our sample data
        data_json = json.dumps(SAMPLE_CHAMP_DATA)
        m = mock_open(read_data=data_json)
        with patch('builtins.open', m):
            with patch('json.load', return_value=SAMPLE_CHAMP_DATA):
                with patch('json.dump'):
                    self.assets._load_champion_data()

        self.assertIn("Aatrox", self.assets.champ_data)
        self.assertEqual(self.assets.id_to_key[266], "Aatrox")
        self.assertEqual(self.assets.name_to_id["aatrox"], 266)

    @patch('os.path.exists', return_value=True)
    def test_load_champion_data_cache_hit(self, mock_exists):
        """When cache file exists, load from disk without downloading."""
        self.assets.session = MagicMock()
        self.assets.ddragon_ver = "14.4.1"

        with patch('builtins.open', mock_open()):
            with patch('json.load', return_value=SAMPLE_CHAMP_DATA):
                self.assets._load_champion_data()

        self.assertIn("Aatrox", self.assets.champ_data)
        self.assertEqual(self.assets.id_to_key[266], "Aatrox")
        self.assertEqual(self.assets.name_to_id["aatrox"], 266)
        # Should NOT have called session.get since cache exists
        self.assets.session.get.assert_not_called()

    def test_preload_champion_icons(self):
        """Test preloading champion icons queues background downloads."""
        self.assets.id_to_key = {266: "Aatrox", 103: "Ahri"}
        with patch.object(self.assets, '_start_download') as mock_start:
            with patch('os.path.exists', return_value=False):
                self.assets.preload_champion_icons()
                # Give daemon thread a brief tick to run
                import time
                time.sleep(0.05)
                self.assertTrue(mock_start.called)

    def test_get_icon_async_with_callback(self):
        """Test async icon fetching invokes callback when image is ready."""
        mock_callback = MagicMock()
        with patch.object(self.assets, 'get_icon', return_value="mock_headless_img"):
            self.assets.get_icon_async("champion", "Aatrox", mock_callback)
            mock_callback.assert_called_once_with("mock_headless_img")

if __name__ == '__main__':
    unittest.main()
