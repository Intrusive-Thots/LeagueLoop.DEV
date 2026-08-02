import unittest
from unittest.mock import MagicMock, patch
import time

from services.api_handler import LCUClient
from core.events import EventBus

class TestLCUReconnect(unittest.TestCase):
    def setUp(self):
        self.client = LCUClient()

    @patch('services.api_handler.scan_clients')
    def test_connection_state_transitions(self, mock_scan):
        """Verify connection state changes and EventBus notifications."""
        # 1. Failed scan
        mock_scan.return_value = {"league": {"connected": False}}
        self.client._last_scan_time = 0.0
        connected_events = []
        
        def _on_connected(val):
            connected_events.append(val)
            
        EventBus.on("lcu_connected", _on_connected)
        
        result = self.client.connect(silent=True)
        self.assertFalse(result)
        self.assertFalse(self.client.is_connected)

        # 2. Successful scan
        mock_scan.return_value = {
            "league": {
                "connected": True,
                "port": "12345",
                "token": "test_auth_token",
                "pid": 9999
            }
        }
        self.client._last_scan_time = 0.0
        result = self.client.connect(silent=True)
        self.assertTrue(result)
        self.assertTrue(self.client.is_connected)
        self.assertEqual(self.client.port, "12345")
        self.assertEqual(self.client.auth_token, "test_auth_token")
        self.assertIn(True, connected_events)

    def test_offline_queue_on_disconnect(self):
        """Mutating requests are queued when offline up to max limit."""
        self.client.is_connected = False
        with patch.object(self.client, 'connect', return_value=False):
            # Send requests while offline
            for i in range(60):
                self.client.request("POST", f"/endpoint_{i}", {"data": i}, silent=True)
                
            self.assertEqual(len(self.client._offline_queue), self.client._offline_queue_max)
            self.assertEqual(self.client._offline_queue[0][1], "/endpoint_0")

    @patch('services.api_handler.scan_clients')
    def test_offline_queue_flushing(self, mock_scan):
        """Offline queue flushes on successful reconnection."""
        mock_scan.return_value = {
            "league": {
                "connected": True,
                "port": "12345",
                "token": "test_token",
                "pid": 1111
            }
        }
        self.client._offline_queue = [
            ("POST", "/lol-lobby/v2/lobby", {"queueId": 420})
        ]
        self.client.is_connected = False
        self.client._last_scan_time = 0.0
        
        with patch.object(self.client.session, 'request') as mock_req:
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_req.return_value = mock_res
            
            res = self.client.request("GET", "/lol-summoner/v1/current-summoner", silent=True)
            # Queue should be emptied after connection
            self.assertEqual(len(self.client._offline_queue), 0)

    def test_backoff_reset(self):
        """Exponential backoff increments on failure and resets to 1.0 on success."""
        self.client._backoff = 1.8
        with patch('services.api_handler.scan_clients') as mock_scan:
            mock_scan.return_value = {
                "league": {
                    "connected": True,
                    "port": "54321",
                    "token": "tok",
                    "pid": 5555
                }
            }
            self.client._last_scan_time = 0.0
            self.client.connect(silent=True)
            self.assertEqual(self.client._backoff, 1.0)

    def test_sleep_wake_backoff_detection(self):
        """Detects time gap > 15s from sleep/wake and resets backoff strategy."""
        self.client._backoff = 2.0
        self.client._last_scan_time = time.time() - 30.0  # 30s ago (sleep gap)
        with patch('services.api_handler.scan_clients') as mock_scan:
            mock_scan.return_value = {"league": {"connected": False}}
            self.client.connect(silent=True)
            self.assertEqual(self.client._backoff, 1.2)  # Reset to 1.0 then 1.0 * 1.2 = 1.2 on failure

    def test_reset_sleep_wake_backoff_method(self):
        """Explicit method reset_sleep_wake_backoff resets backoff and last scan timestamp."""
        self.client._backoff = 2.0
        self.client._last_scan_time = 999.0
        self.client.reset_sleep_wake_backoff()
        self.assertEqual(self.client._backoff, 1.0)
        self.assertEqual(self.client._last_scan_time, 0.0)

if __name__ == '__main__':
    unittest.main()
