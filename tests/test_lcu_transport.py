import unittest
from unittest.mock import MagicMock, patch

from services.lcu_transport import LCUTransport
from core.events import EventBus, LCUConnectionEvent


class TestLCUTransport(unittest.TestCase):

    def setUp(self):
        self.transport = LCUTransport()

    @patch("services.lcu_transport.scan_clients")
    def test_connect_success(self, mock_scan):
        mock_scan.return_value = {
            "league": {
                "connected": True,
                "port": "25280",
                "token": "testtoken123",
                "auth_token": "testtoken123"
            }
        }
        mock_res = MagicMock()
        mock_res.status_code = 200
        self.transport.session.get = MagicMock(return_value=mock_res)

        events_captured = []
        handle = EventBus.on(LCUConnectionEvent, lambda ev: events_captured.append(ev))

        connected = self.transport.connect()
        self.assertTrue(connected)
        self.assertTrue(self.transport.is_connected)
        self.assertEqual(self.transport.port, "25280")
        self.assertEqual(len(events_captured), 1)
        self.assertTrue(events_captured[0].connected)

        handle.unsubscribe()

    @patch("services.lcu_transport.scan_clients")
    def test_connect_failure_when_client_disconnected(self, mock_scan):
        mock_scan.return_value = {"league": {"connected": False}}
        self.transport._last_scan_time = 0.0
        self.transport._backoff = 0.0

        connected = self.transport.connect()
        self.assertFalse(connected)
        self.assertFalse(self.transport.is_connected)


if __name__ == "__main__":
    unittest.main()
