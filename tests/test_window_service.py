import unittest
from unittest.mock import MagicMock, patch
from core.events import EventBus
from services.window_service import WindowService

class TestWindowService(unittest.TestCase):
    def setUp(self):
        EventBus._listeners.clear()
        self.mock_settings = MagicMock()
        self.mock_settings.get.return_value = True

    def test_initialization(self):
        service = WindowService(self.mock_settings)
        self.assertTrue(service.is_docked)
        self.mock_settings.get.assert_called_with("docked_mode", True)

    def test_set_docked_mode(self):
        service = WindowService(self.mock_settings)
        mock_emit = MagicMock()
        with patch.object(EventBus, "emit", mock_emit):
            service.set_docked_mode(False)
            self.assertFalse(service.is_docked)
            self.mock_settings.set.assert_called_once_with("docked_mode", False)
            mock_emit.assert_any_call("docked_mode_changed", False)

    def test_on_docked_mode_setting_changed(self):
        service = WindowService(self.mock_settings)
        
        # Emit setting changed normally so the listener triggers
        EventBus.emit("setting_changed:docked_mode", False)
        self.assertFalse(service.is_docked)
        self.mock_settings.set.assert_called_once_with("docked_mode", False)

    def test_register_unregister_window(self):
        service = WindowService(self.mock_settings)
        geom_cb = MagicMock()
        state_cb = MagicMock()
        
        service.register_window(12345, geom_cb, state_cb)
        self.assertIn(12345, service._registered_windows)
        self.assertEqual(service._registered_windows[12345]["geom_cb"], geom_cb)
        
        service.unregister_window(12345)
        self.assertNotIn(12345, service._registered_windows)

    @patch("threading.Thread")
    def test_start_stop(self, mock_thread):
        service = WindowService(self.mock_settings)
        service.start()
        self.assertTrue(service._running)
        mock_thread.assert_called_once()
        
        service.stop()
        self.assertFalse(service._running)
