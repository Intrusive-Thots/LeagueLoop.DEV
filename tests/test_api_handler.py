import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from services.api_handler import LCUClient

class TestLCUClient(unittest.TestCase):
    def setUp(self):
        self.client = LCUClient()

    def test_init(self):
        self.assertFalse(self.client.is_connected)
        self.assertIsNone(self.client.port)
        self.assertIsNone(self.client.auth_token)

    @patch('services.api_handler.psutil.process_iter')
    def test_connect_success(self, mock_process_iter):
        """Test connect via cmdline extraction (primary path)."""
        mock_proc = MagicMock()
        mock_proc.info = {'name': 'LeagueClientUx.exe'}
        mock_proc.pid = 12345
        mock_proc.is_running.return_value = True
        mock_proc.name.return_value = 'LeagueClientUx.exe'
        mock_proc.cmdline.return_value = [
            "LeagueClientUx.exe",
            "--app-port=54321",
            "--remoting-auth-token=password",
        ]
        mock_process_iter.return_value = [mock_proc]

        # Override cooldown
        self.client._last_scan_time = 0
        self.client._backoff = 0

        self.assertTrue(self.client.connect())
        self.assertTrue(self.client.is_connected)
        self.assertEqual(self.client.port, "54321")
        self.assertEqual(self.client.auth_token, "password")

    def test_request_success(self):
        """Test request sends through session and returns response."""
        self.client.is_connected = True
        self.client.port = "1234"
        self.client.base_url = "https://127.0.0.1:1234"
        self.client.headers = {"Authorization": "Basic xxx"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        self.client.session = MagicMock()
        self.client.session.request.return_value = mock_response

        result = self.client.request("GET", "/test", silent=True)
        self.assertEqual(result, mock_response)
        self.client.session.request.assert_called_once()

    def test_request_not_connected(self):
        self.client.is_connected = False
        with patch.object(self.client, 'connect', return_value=False) as mock_connect:
            result = self.client.request("GET", "/test")
            self.assertIsNone(result)
            mock_connect.assert_called_once()

if __name__ == '__main__':
    unittest.main()
