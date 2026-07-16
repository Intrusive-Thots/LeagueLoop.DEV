import unittest
from unittest.mock import MagicMock, patch
from core.events import EventBus
from services.notification_service import NotificationService, get_notification_service

class TestNotificationService(unittest.TestCase):
    def setUp(self):
        EventBus._listeners.clear()

    def test_show(self):
        service = NotificationService()
        mock_emit = MagicMock()
        with patch.object(EventBus, "emit", mock_emit):
            service.show("Hello", icon="🔥", theme="danger", confetti=True)
            
            history = service.get_history()
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["message"], "Hello")
            self.assertEqual(history[0]["icon"], "🔥")
            
            mock_emit.assert_any_call("show_toast", "Hello", "🔥", "danger", True)
            mock_emit.assert_any_call("notification_received", history[0])

    def test_history_cap(self):
        service = NotificationService()
        service._max_history = 3
        
        for i in range(5):
            service.show(f"Msg {i}")
            
        history = service.get_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["message"], "Msg 2")
        self.assertEqual(history[-1]["message"], "Msg 4")

    def test_helpers(self):
        service = NotificationService()
        with patch.object(service, "show") as mock_show:
            service.success("ok")
            mock_show.assert_called_with("ok", icon="✓", theme="success", confetti=False)
            
            service.error("fail")
            mock_show.assert_called_with("fail", icon="⚠️", theme="error")
            
            service.warning("warn")
            mock_show.assert_called_with("warn", icon="⚠️", theme="warning")
            
            service.info("note")
            mock_show.assert_called_with("note", icon="ℹ", theme="primary")

    def test_clear_history(self):
        service = NotificationService()
        service.show("Msg")
        self.assertEqual(len(service.get_history()), 1)
        
        mock_emit = MagicMock()
        with patch.object(EventBus, "emit", mock_emit):
            service.clear_history()
            self.assertEqual(len(service.get_history()), 0)
            mock_emit.assert_called_once_with("notification_history_cleared")

    def test_singleton(self):
        with patch("services.notification_service._instance", None):
            inst1 = get_notification_service()
            inst2 = get_notification_service()
            self.assertIs(inst1, inst2)
