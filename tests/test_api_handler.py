import unittest
import time
from unittest.mock import MagicMock, patch, PropertyMock

from services.api_handler import LCUClient

class TestLCUClient(unittest.TestCase):
    def setUp(self):
        self.client = LCUClient()

    def test_init(self):
        self.assertFalse(self.client.is_connected)
        self.assertIsNone(self.client.port)
        self.assertIsNone(self.client.auth_token)

    @patch('services.api_handler.scan_clients')
    def test_connect_success(self, mock_scan):
        """Test connect via scan_clients."""
        mock_scan.return_value = {
            "league": {
                "connected": True,
                "port": "54321",
                "token": "password",
                "auth_token": "password",
                "pid": 12345,
            }
        }

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

    def test_request_diagnostics_and_throttling(self):
        """Test rate-limit throttle & retry status diagnostics tracking."""
        diag_init = self.client.get_request_diagnostics()
        self.assertEqual(diag_init["total_requests"], 0)
        self.assertEqual(diag_init["rate_limit_throttles"], 0)
        self.assertEqual(diag_init["http_429_count"], 0)

        self.client.is_connected = True
        self.client.port = "1234"
        self.client.base_url = "https://127.0.0.1:1234"

        # Simulate response with HTTP 429
        mock_response = MagicMock()
        mock_response.status_code = 429
        self.client.session = MagicMock()
        self.client.session.request.return_value = mock_response

        res = self.client.request("GET", "/lol-champ-select/v1/session", silent=True)
        self.assertEqual(res, mock_response)

        diag = self.client.get_request_diagnostics()
        self.assertEqual(diag["total_requests"], 1)
        self.assertEqual(diag["http_429_count"], 1)

        # Force token bucket depletion to trigger throttle sleep tracking
        now = time.time()
        self.client._last_token_update = now
        self.client._tokens = 0.0
        mock_response.status_code = 200

        with patch('time.sleep') as mock_sleep:
            res2 = self.client.request("GET", "/lol-summoner/v1/current-summoner", silent=True)
            self.assertEqual(res2, mock_response)
            mock_sleep.assert_called_once()

        diag_after = self.client.get_request_diagnostics()
        self.assertEqual(diag_after["total_requests"], 2)
        self.assertEqual(diag_after["rate_limit_throttles"], 1)
        self.assertGreater(diag_after["total_throttle_sleep_s"], 0)

    def test_adaptive_http_timeout_and_latency_histogram(self):
        """Test HTTP request latency recording, adaptive timeout calculation, and histogram."""
        self.assertEqual(self.client.get_adaptive_http_timeout(), 2.0)

        # Record multiple latencies
        for lat in [15.0, 25.0, 30.0, 45.0, 60.0, 120.0]:
            self.client._record_http_latency(lat)

        hist = self.client.get_http_latency_histogram()
        self.assertEqual(hist["sample_count"], 6)
        self.assertEqual(hist["min_latency_ms"], 15.0)
        self.assertEqual(hist["max_latency_ms"], 120.0)
        self.assertIn("10-50ms", hist["buckets"])
        self.assertGreaterEqual(hist["buckets"]["10-50ms"], 4)

        adaptive_timeout = self.client.get_adaptive_http_timeout()
        self.assertGreaterEqual(adaptive_timeout, 1.5)
        self.assertLessEqual(adaptive_timeout, 8.0)

        diag = self.client.get_request_diagnostics()
        self.assertIn("adaptive_timeout_s", diag)
        self.assertIn("avg_latency_ms", diag)

    def test_http_5xx_retry_jitter_backoff(self):
        """Test HTTP 5xx transient server error retries with exponential jitter backoff."""
        self.client.is_connected = True
        self.client.port = "1234"
        self.client.base_url = "https://127.0.0.1:1234"

        # Mock 500 error response on 1st call, 200 OK on 2nd call
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_200 = MagicMock()
        resp_200.status_code = 200

        self.client.session = MagicMock()
        self.client.session.request.side_effect = [resp_500, resp_200]

        with patch('time.sleep') as mock_sleep:
            res = self.client.request("GET", "/lol-gameflow/v1/session", silent=True)
            self.assertEqual(res, resp_200)
            self.assertEqual(self.client.session.request.call_count, 2)
            mock_sleep.assert_called_once()
            # Verify sleep duration is jittered base backoff (~0.05 - 0.1s)
            sleep_duration = mock_sleep.call_args[0][0]
            self.assertGreaterEqual(sleep_duration, 0.05)
            self.assertLessEqual(sleep_duration, 0.15)

        diag = self.client.get_request_diagnostics()
        self.assertEqual(diag["http_5xx_count"], 1)
        self.assertEqual(diag["http_retry_count"], 1)

    def test_http_status_code_distribution_and_error_telemetry(self):
        """Test HTTP response status distribution diagnostics & 4xx/5xx error telemetry logging for Task 151."""
        self.client.is_connected = True
        self.client.port = "1234"
        self.client.base_url = "https://127.0.0.1:1234"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_404 = MagicMock()
        resp_404.status_code = 404
        resp_503 = MagicMock()
        resp_503.status_code = 503

        self.client.session = MagicMock()
        self.client.session.request.side_effect = [resp_200, resp_404, resp_503, resp_503, resp_503, resp_200]

        # 1st request -> 200 OK
        res1 = self.client.request("GET", "/lol-summoner/v1/current-summoner", silent=True)
        self.assertEqual(res1, resp_200)

        # 2nd request -> 404 Not Found
        res2 = self.client.request("GET", "/lol-match-history/v1/games/invalid", silent=True)
        self.assertEqual(res2, resp_404)

        # 3rd request -> 503 Service Unavailable
        with patch('time.sleep'):
            res3 = self.client.request("POST", "/lol-champ-select/v1/session/actions/1/complete", silent=True)

        # 4th request -> 200 OK
        res4 = self.client.request("GET", "/lol-chat/v1/me", silent=True)
        self.assertEqual(res4, resp_200)

        telemetry = self.client.get_http_status_telemetry()
        self.assertGreaterEqual(telemetry["total_requests"], 4)
        self.assertIn("200", telemetry["status_code_distribution"])
        self.assertIn("404", telemetry["status_code_distribution"])
        self.assertEqual(telemetry["http_2xx_count"], 2)
        self.assertEqual(telemetry["http_4xx_count"], 1)
        self.assertGreaterEqual(telemetry["http_5xx_count"], 1)
        self.assertGreater(telemetry["http_error_rate_pct"], 0.0)
        self.assertGreaterEqual(telemetry["recent_errors_count"], 2)

        diag = self.client.get_request_diagnostics()
        self.assertIn("status_code_distribution", diag)
        self.assertEqual(diag["http_2xx_count"], 2)
        self.assertEqual(diag["http_4xx_count"], 1)

    def test_offline_retry_queue_telemetry_and_diagnostics(self):
        """Test offline request retry queue telemetry & execution success diagnostics for Task 154."""
        self.client.is_connected = False
        self.client.connect = MagicMock(return_value=False)

        # Queue mutation requests while offline
        self.client.request("POST", "/lol-lobby/v2/lobby", {"queueId": 420}, silent=True)
        self.client.request("POST", "/lol-champ-select/v1/session/actions/1/complete", silent=True)

        telemetry = self.client.get_offline_retry_telemetry()
        self.assertEqual(telemetry["current_queue_len"], 2)
        self.assertEqual(telemetry["queued_count"], 2)
        self.assertEqual(telemetry["executed_count"], 0)

        # Simulate reconnect and execution with success mock response
        resp_200 = MagicMock()
        resp_200.status_code = 200
        self.client.request = MagicMock(return_value=resp_200)

        # Directly call _execute_offline_retry
        self.client._execute_offline_retry("POST", "/lol-lobby/v2/lobby", {"queueId": 420})

        telemetry_after = self.client.get_offline_retry_telemetry()
        self.assertEqual(telemetry_after["success_count"], 1)

        diag = self.client.get_request_diagnostics()
        self.assertIn("offline_retry_queued", diag)
        self.assertIn("offline_retry_success_count", diag)

    def test_websocket_subscription_filter_and_dispatch_telemetry(self):
        """Test websocket subscription filter performance metrics & dispatch telemetry for Task 157."""
        dummy_cb1 = MagicMock()
        dummy_cb2 = MagicMock()

        self.client.subscribe("OnJsonApiEvent_lol_gameflow_v1_gameflow_phase", dummy_cb1)
        self.client.subscribe("OnJsonApiEvent_lol_champ_select_v1_session", dummy_cb2)

        dispatch_meta1 = self.client.get_ws_dispatch_telemetry()
        self.assertGreaterEqual(dispatch_meta1["active_subscription_filters"], 2)
        self.assertGreaterEqual(dispatch_meta1["total_registered_listeners"], 2)
        self.assertEqual(dispatch_meta1["dispatch_event_count"], 0)

        # Simulate callback dispatch recording
        self.client._record_ws_dispatch_telemetry("OnJsonApiEvent_lol_gameflow_v1_gameflow_phase", 1, 0.45)
        self.client._record_ws_dispatch_telemetry("OnJsonApiEvent_lol_champ_select_v1_session", 1, 0.85)

        dispatch_meta2 = self.client.get_ws_dispatch_telemetry()
        self.assertEqual(dispatch_meta2["dispatch_event_count"], 2)
        self.assertEqual(dispatch_meta2["dispatched_callbacks_count"], 2)
        self.assertGreater(dispatch_meta2["avg_dispatch_latency_ms"], 0.0)

        ws_meta = self.client.get_ws_telemetry()
        self.assertIn("active_subscription_filters", ws_meta)
        self.assertIn("dispatched_callbacks_count", ws_meta)

    def test_http_status_distribution_anomaly_threshold_alerts(self):
        """Test automated HTTP response status distribution anomaly threshold alerts for Task 169."""
        initial_telemetry = self.client.get_http_status_anomaly_telemetry()
        self.assertEqual(initial_telemetry["http_status_anomaly_count"], 0)
        self.assertFalse(initial_telemetry["http_status_anomaly_active"])
        self.assertIn("http_anomaly_error_rate_threshold_pct", initial_telemetry)

        # Simulate normal 200 responses
        for _ in range(10):
            self.client._record_http_status_code(200, "GET", "/lol-summoner/v1/current-summoner")

        tel_200 = self.client.get_http_status_anomaly_telemetry()
        self.assertFalse(tel_200["http_status_anomaly_active"])

        # Trigger HTTP 5xx anomaly threshold
        for _ in range(5):
            self.client._record_http_status_code(500, "POST", "/lol-lobby/v2/lobby")

        tel_500 = self.client.get_http_status_anomaly_telemetry()
        self.assertTrue(tel_500["http_status_anomaly_active"])
        self.assertGreater(tel_500["http_status_anomaly_count"], 0)
        self.assertIsNotNone(tel_500["last_http_status_anomaly"])

        full_status_telemetry = self.client.get_http_status_telemetry()
        self.assertIn("http_status_anomaly_active", full_status_telemetry)
        self.assertIn("http_status_anomaly_count", full_status_telemetry)

if __name__ == '__main__':
    unittest.main()

