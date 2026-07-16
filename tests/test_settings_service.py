import unittest
from unittest.mock import MagicMock, patch
from core.events import EventBus
from services.settings_service import SettingsService, get_settings_service

class TestSettingsService(unittest.TestCase):
    def setUp(self):
        EventBus._listeners.clear()
        self.mock_config = MagicMock()

    def test_get(self):
        self.mock_config.get.return_value = "fizz"
        service = SettingsService(self.mock_config)
        
        self.assertEqual(service.get("some_key"), "fizz")
        self.mock_config.get.assert_called_once_with("some_key", None)

    def test_set(self):
        self.mock_config.get.return_value = "old"
        service = SettingsService(self.mock_config)
        
        mock_emit = MagicMock()
        with patch.object(EventBus, "emit", mock_emit):
            service.set("some_key", "new")
            self.mock_config.set.assert_called_once_with("some_key", "new", save=True)
            mock_emit.assert_any_call("setting_changed:some_key", "new")

    def test_set_no_change(self):
        self.mock_config.get.return_value = "same"
        service = SettingsService(self.mock_config)
        
        mock_emit = MagicMock()
        with patch.object(EventBus, "emit", mock_emit):
            service.set("some_key", "same")
            self.mock_config.set.assert_not_called()
            mock_emit.assert_not_called()

    def test_set_batch(self):
        self.mock_config.get.return_value = "old"
        service = SettingsService(self.mock_config)
        
        updates = {"key1": "val1", "key2": "val2"}
        service.set_batch(updates, save=True)
        
        self.mock_config.set.assert_any_call("key1", "val1", save=False)
        self.mock_config.set.assert_any_call("key2", "val2", save=False)
        self.mock_config.save.assert_called_once()

    def test_singleton(self):
        with patch("services.settings_service._instance", None):
            inst1 = get_settings_service(self.mock_config)
            inst2 = get_settings_service()
            self.assertIs(inst1, inst2)
