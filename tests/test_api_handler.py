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
        """Test sliding-window HTTP anomaly alerts (no spam on successful 200s)."""
        initial_telemetry = self.client.get_http_status_anomaly_telemetry()
        self.assertEqual(initial_telemetry["http_status_anomaly_count"], 0)
        self.assertFalse(initial_telemetry["http_status_anomaly_active"])
        self.assertIn("http_anomaly_error_rate_threshold_pct", initial_telemetry)

        # Simulate normal 200 responses — must never flag anomaly
        for _ in range(10):
            self.client._record_http_status_code(200, "GET", "/lol-summoner/v1/current-summoner")

        tel_200 = self.client.get_http_status_anomaly_telemetry()
        self.assertFalse(tel_200["http_status_anomaly_active"])
        self.assertEqual(tel_200["http_status_anomaly_count"], 0)

        # Trigger HTTP 5xx anomaly threshold (5 hard fails)
        for _ in range(5):
            self.client._record_http_status_code(500, "POST", "/lol-lobby/v2/lobby")

        tel_500 = self.client.get_http_status_anomaly_telemetry()
        self.assertTrue(tel_500["http_status_anomaly_active"])
        self.assertGreater(tel_500["http_status_anomaly_count"], 0)
        self.assertIsNotNone(tel_500["last_http_status_anomaly"])

        # Successful 200s after failures must not re-alert / keep counting spam
        before = tel_500["http_status_anomaly_count"]
        for _ in range(20):
            self.client._record_http_status_code(200, "GET", "/lol-gameflow/v1/gameflow-phase")
        tel_after_ok = self.client.get_http_status_anomaly_telemetry()
        self.assertEqual(tel_after_ok["http_status_anomaly_count"], before)
        self.assertFalse(tel_after_ok["http_status_anomaly_active"])

        full_status_telemetry = self.client.get_http_status_telemetry()
        self.assertIn("http_status_anomaly_active", full_status_telemetry)
        self.assertIn("http_status_anomaly_count", full_status_telemetry)

    def test_in_game_mode_ws_stale_timeout(self):
        """In-game mode raises WS stale timeout so quiet LCU periods don't reconnect-storm."""
        base = self.client._effective_ws_stale_timeout()
        self.client.set_in_game_mode(True)
        self.assertTrue(self.client._in_game_mode)
        self.assertGreater(self.client._effective_ws_stale_timeout(), base)
        self.client.set_in_game_mode(False)
        self.assertFalse(self.client._in_game_mode)
        self.assertEqual(self.client._effective_ws_stale_timeout(), base)

    def test_http_latency_variance_telemetry(self):
        """Test HTTP request latency variance calculation & telemetry for Task 172."""
        empty_tel = self.client.get_http_latency_variance_telemetry()
        self.assertEqual(empty_tel["http_latency_variance_ms2"], 0.0)
        self.assertEqual(empty_tel["http_latency_stddev_ms"], 0.0)
        self.assertEqual(empty_tel["http_latency_cv"], 0.0)
        self.assertEqual(empty_tel["http_latency_sample_count"], 0)

        # Record samples: 10ms, 20ms, 30ms -> Mean = 20ms, Var = (100 + 0 + 100)/3 = 66.6667ms^2, StdDev = 8.165ms
        self.client._record_http_latency(10.0)
        self.client._record_http_latency(20.0)
        self.client._record_http_latency(30.0)

        var_tel = self.client.get_http_latency_variance_telemetry()
        self.assertAlmostEqual(var_tel["http_latency_variance_ms2"], 66.6667, places=3)
        self.assertAlmostEqual(var_tel["http_latency_stddev_ms"], 8.165, places=3)
        self.assertGreater(var_tel["http_latency_cv"], 0.0)
        self.assertEqual(var_tel["http_latency_sample_count"], 3)

        hist = self.client.get_http_latency_histogram()
        self.assertIn("http_latency_variance_ms2", hist)
        self.assertIn("http_latency_stddev_ms", hist)
        self.assertIn("http_latency_cv", hist)

        diag = self.client.get_request_diagnostics()
        self.assertIn("http_latency_variance_ms2", diag)
        self.assertIn("http_latency_stddev_ms", diag)

    def test_http_latency_confidence_interval_telemetry(self):
        """Test automated HTTP client response latency standard error & confidence interval metrics for Task 175."""
        empty_ci = self.client.get_http_latency_confidence_interval_telemetry()
        self.assertEqual(empty_ci["http_latency_mean_ms"], 0.0)
        self.assertEqual(empty_ci["http_latency_stderr_ms"], 0.0)
        self.assertEqual(empty_ci["http_latency_ci_margin_ms"], 0.0)
        self.assertEqual(empty_ci["confidence_level"], 0.95)
        self.assertEqual(empty_ci["sample_count"], 0)

        # Record latency samples: 10ms, 20ms, 30ms -> Mean = 20ms, Sample StdDev = sqrt(100) = 10.0, StdErr = 10 / sqrt(3) = 5.7735
        self.client._record_http_latency(10.0)
        self.client._record_http_latency(20.0)
        self.client._record_http_latency(30.0)

        ci_tel = self.client.get_http_latency_confidence_interval_telemetry(0.95)
        self.assertEqual(ci_tel["sample_count"], 3)
        self.assertAlmostEqual(ci_tel["http_latency_mean_ms"], 20.0, places=2)
        self.assertAlmostEqual(ci_tel["http_latency_stderr_ms"], 5.7735, places=3)
        self.assertGreater(ci_tel["http_latency_ci_margin_ms"], 0.0)
        self.assertLessEqual(ci_tel["http_latency_ci_lower_ms"], 20.0)
        self.assertGreaterEqual(ci_tel["http_latency_ci_upper_ms"], 20.0)

        hist = self.client.get_http_latency_histogram()
        self.assertIn("http_latency_stderr_ms", hist)
        self.assertIn("http_latency_ci_margin_ms", hist)
        self.assertIn("http_latency_ci_lower_ms", hist)
        self.assertIn("http_latency_ci_upper_ms", hist)

    def test_http_retry_jitter_entropy_telemetry(self):
        """Test automated HTTP request retry exponential backoff jitter entropy telemetry for Task 181."""
        empty_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertEqual(empty_tel["http_retry_jitter_samples_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_entropy_bits"], 0.0)

        # Record multiple jitter samples
        self.client._record_http_retry_jitter(0.015)
        self.client._record_http_retry_jitter(0.025)
        self.client._record_http_retry_jitter(0.035)

        tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertEqual(tel["http_retry_jitter_samples_count"], 3)
        self.assertGreater(tel["http_retry_jitter_entropy_bits"], 0.0)
        self.assertEqual(tel["http_retry_jitter_min_s"], 0.015)
        self.assertEqual(tel["http_retry_jitter_max_s"], 0.035)

        diag = self.client.get_request_diagnostics()
        self.assertIn("http_retry_jitter_entropy_bits", diag)

    def test_http_retry_jitter_variance_telemetry(self):
        """Test automated HTTP request retry exponential backoff jitter variance & stddev telemetry for Task 190."""
        empty_tel = self.client.get_http_retry_jitter_variance_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_variance"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_stddev_ms"], 0.0)

        # Single sample -> not enough for variance
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_variance_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_variance"], 0.0)

        # Additional samples
        self.client._record_http_retry_jitter(0.04)
        self.client._record_http_retry_jitter(0.06)

        var_tel = self.client.get_http_retry_jitter_variance_telemetry()
        self.assertEqual(var_tel["sample_count"], 3)
        self.assertGreater(var_tel["http_retry_jitter_variance"], 0.0)
        self.assertGreater(var_tel["http_retry_jitter_stddev_ms"], 0.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_variance", entropy_tel)
        self.assertIn("http_retry_jitter_stddev_ms", entropy_tel)

    def test_http_retry_jitter_geometric_harmonic_means_telemetry(self):
        """Test automated HTTP request retry exponential backoff jitter geometric mean & harmonic mean telemetry for Task 202."""
        empty_tel = self.client.get_http_retry_jitter_geometric_harmonic_means_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_geometric_mean_s"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_harmonic_mean_s"], 0.0)

        # Record multiple positive jitter samples: 0.02, 0.04, 0.08
        self.client._record_http_retry_jitter(0.02)
        self.client._record_http_retry_jitter(0.04)
        self.client._record_http_retry_jitter(0.08)

        tel = self.client.get_http_retry_jitter_geometric_harmonic_means_telemetry()
        self.assertEqual(tel["sample_count"], 3)
        self.assertGreater(tel["http_retry_jitter_geometric_mean_s"], 0.0)
        self.assertGreater(tel["http_retry_jitter_harmonic_mean_s"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_harmonic_mean_s"], tel["http_retry_jitter_geometric_mean_s"])

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_geometric_mean_s", entropy_tel)
        self.assertIn("http_retry_jitter_harmonic_mean_s", entropy_tel)

    def test_http_retry_jitter_rse_variance_ratio_telemetry(self):
        """Test automated HTTP request retry exponential backoff jitter relative standard error & variance ratio telemetry for Task 208."""
        empty_tel = self.client.get_http_retry_jitter_rse_variance_ratio_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_rse_pct"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_variance_ratio"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_signal_to_noise_ratio"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_rse_variance_ratio_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_rse_pct"], 0.0)

        # Multiple samples
        self.client._record_http_retry_jitter(0.04)
        self.client._record_http_retry_jitter(0.06)

        tel = self.client.get_http_retry_jitter_rse_variance_ratio_telemetry()
        self.assertEqual(tel["sample_count"], 3)
        self.assertGreater(tel["http_retry_jitter_rse_pct"], 0.0)
        self.assertGreater(tel["http_retry_jitter_variance_ratio"], 0.0)
        self.assertGreater(tel["http_retry_jitter_signal_to_noise_ratio"], 0.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_rse_pct", entropy_tel)
        self.assertIn("http_retry_jitter_variance_ratio", entropy_tel)
        self.assertIn("http_retry_jitter_signal_to_noise_ratio", entropy_tel)

    def test_http_retry_jitter_cv_fano_ci_telemetry(self):
        """Test automated HTTP request retry exponential backoff jitter CV & Fano factor confidence interval telemetry for Task 211."""
        empty_tel = self.client.get_http_retry_jitter_cv_fano_ci_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_cv"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_fano"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_cv_fano_ci_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_cv"], 0.0)

        # Multiple samples
        self.client._record_http_retry_jitter(0.04)
        self.client._record_http_retry_jitter(0.06)

        tel = self.client.get_http_retry_jitter_cv_fano_ci_telemetry()
        self.assertEqual(tel["sample_count"], 3)
        self.assertGreater(tel["http_retry_jitter_cv"], 0.0)
        self.assertGreater(tel["http_retry_jitter_cv_stderr"], 0.0)
        self.assertGreater(tel["http_retry_jitter_cv_ci_margin"], 0.0)
        self.assertGreater(tel["http_retry_jitter_fano"], 0.0)
        self.assertGreater(tel["http_retry_jitter_fano_stderr"], 0.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_cv", entropy_tel)
        self.assertIn("http_retry_jitter_fano", entropy_tel)

    def test_http_retry_jitter_mad_telemetry(self):
        """Test automated HTTP request retry exponential backoff jitter MAD & MedAD telemetry for Task 214."""
        empty_tel = self.client.get_http_retry_jitter_mad_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_mad_s"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_medad_s"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_mad_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_mad_s"], 0.0)

        # Multiple samples
        self.client._record_http_retry_jitter(0.04)
        self.client._record_http_retry_jitter(0.06)

        tel = self.client.get_http_retry_jitter_mad_telemetry()
        self.assertEqual(tel["sample_count"], 3)
        self.assertGreater(tel["http_retry_jitter_mad_s"], 0.0)
        self.assertGreater(tel["http_retry_jitter_mad_ms"], 0.0)
        self.assertGreater(tel["http_retry_jitter_relative_mad_pct"], 0.0)
        self.assertGreater(tel["http_retry_jitter_medad_s"], 0.0)
        self.assertGreater(tel["http_retry_jitter_medad_ms"], 0.0)
        self.assertGreater(tel["http_retry_jitter_normal_scaled_medad_s"], 0.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_mad_s", entropy_tel)
        self.assertIn("http_retry_jitter_medad_s", entropy_tel)

    def test_http_retry_jitter_gini_hoover_telemetry(self):
        """Task 217: Test automated HTTP request retry exponential backoff jitter Gini coefficient & Hoover index inequality telemetry."""
        # Initial state (empty)
        empty_tel = self.client.get_http_retry_jitter_gini_hoover_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_gini_coefficient"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_hoover_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_relative_mean_difference"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_gini_hoover_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_gini_coefficient"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_hoover_index"], 0.0)

        # Multiple samples with variance
        self.client._record_http_retry_jitter(0.04)
        self.client._record_http_retry_jitter(0.06)

        tel = self.client.get_http_retry_jitter_gini_hoover_telemetry()
        self.assertEqual(tel["sample_count"], 3)
        self.assertGreater(tel["http_retry_jitter_gini_coefficient"], 0.0)
        self.assertGreater(tel["http_retry_jitter_hoover_index"], 0.0)
        self.assertGreater(tel["http_retry_jitter_relative_mean_difference"], 0.0)
        self.assertAlmostEqual(tel["http_retry_jitter_relative_mean_difference"], 2.0 * tel["http_retry_jitter_gini_coefficient"], places=4)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_gini_coefficient", entropy_tel)
        self.assertIn("http_retry_jitter_hoover_index", entropy_tel)
        self.assertIn("http_retry_jitter_relative_mean_difference", entropy_tel)

    def test_http_retry_jitter_theil_atkinson_telemetry(self):
        """Task 220: Test automated HTTP request retry exponential backoff jitter Theil index & Atkinson index inequality telemetry."""
        # Initial state (empty)
        empty_tel = self.client.get_http_retry_jitter_theil_atkinson_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_theil_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_atkinson_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_theil_atkinson_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_theil_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_atkinson_index"], 0.0)

        # Multiple samples with variance
        self.client._record_http_retry_jitter(0.04)
        self.client._record_http_retry_jitter(0.06)

        tel = self.client.get_http_retry_jitter_theil_atkinson_telemetry()
        self.assertEqual(tel["sample_count"], 3)
        self.assertGreater(tel["http_retry_jitter_theil_index"], 0.0)
        self.assertGreater(tel["http_retry_jitter_atkinson_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_atkinson_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_theil_index", entropy_tel)
        self.assertIn("http_retry_jitter_atkinson_index", entropy_tel)

    def test_http_retry_jitter_palma_decile_telemetry(self):
        """Task 223: Test HTTP request retry exponential backoff jitter Palma ratio & Decile ratio inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_palma_decile_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_palma_ratio"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_decile_ratio"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_palma_decile_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_palma_decile_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreater(tel["http_retry_jitter_palma_ratio"], 0.0)
        self.assertGreater(tel["http_retry_jitter_decile_ratio"], 0.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_palma_ratio", entropy_tel)
        self.assertIn("http_retry_jitter_decile_ratio", entropy_tel)

    def test_http_retry_jitter_hoover_ricci_telemetry(self):
        """Task 226: Test HTTP request retry exponential backoff jitter Hoover index & Ricci-Schutz inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_hoover_ricci_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_hoover_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_ricci_schutz_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_hoover_ricci_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_hoover_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_ricci_schutz_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_hoover_ricci_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreater(tel["http_retry_jitter_hoover_index"], 0.0)
        self.assertGreater(tel["http_retry_jitter_ricci_schutz_index"], 0.0)
        self.assertEqual(tel["http_retry_jitter_hoover_index"], tel["http_retry_jitter_ricci_schutz_index"])

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_hoover_index", entropy_tel)
        self.assertIn("http_retry_jitter_ricci_schutz_index", entropy_tel)

    def test_http_retry_jitter_kakwani_reynolds_telemetry(self):
        """Task 229: Test HTTP request retry exponential backoff jitter Kakwani index & Reynolds-Smolensky inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_kakwani_reynolds_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_kakwani_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_reynolds_smolensky_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_kakwani_reynolds_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_kakwani_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_reynolds_smolensky_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_kakwani_reynolds_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_kakwani_index"], 0.0)
        self.assertGreaterEqual(tel["http_retry_jitter_reynolds_smolensky_index"], 0.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_kakwani_index", entropy_tel)
        self.assertIn("http_retry_jitter_reynolds_smolensky_index", entropy_tel)

    def test_http_retry_jitter_kolm_atkinson_gini_telemetry(self):
        """Task 232: Test HTTP request retry exponential backoff jitter Kolm-Pollak index & Atkinson-Gini inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_kolm_atkinson_gini_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_kolm_pollak_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_atkinson_gini_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_kolm_atkinson_gini_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_kolm_pollak_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_atkinson_gini_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_kolm_atkinson_gini_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_kolm_pollak_index"], 0.0)
        self.assertGreaterEqual(tel["http_retry_jitter_atkinson_gini_index"], 0.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_kolm_pollak_index", entropy_tel)
        self.assertIn("http_retry_jitter_atkinson_gini_index", entropy_tel)

    def test_http_retry_jitter_der_zhang_polarization_telemetry(self):
        """Task 241: Test HTTP request retry exponential backoff jitter Duclos-Esteban-Ray (DER) index & Zhang-Kanbur polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_der_zhang_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_der_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_zhang_kanbur_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_der_zhang_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_der_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_zhang_kanbur_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_der_zhang_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_der_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_der_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_zhang_kanbur_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_zhang_kanbur_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_der_index", entropy_tel)
        self.assertIn("http_retry_jitter_zhang_kanbur_index", entropy_tel)

    def test_http_retry_jitter_ch_tw_polarization_telemetry(self):
        """Task 247: Test HTTP request retry exponential backoff jitter Chakravarty (CH) & Tsui-Wang (TW) polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_ch_tw_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_chakravarty_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_tsui_wang_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_ch_tw_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_chakravarty_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_tsui_wang_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_ch_tw_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_chakravarty_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_chakravarty_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_tsui_wang_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_tsui_wang_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_chakravarty_index", entropy_tel)
        self.assertIn("http_retry_jitter_tsui_wang_index", entropy_tel)

    def test_http_retry_jitter_wt_gradin_polarization_telemetry(self):
        """Task 250: Test HTTP request retry exponential backoff jitter Wang-Tsui (WT) & Gradín (GR) polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_wt_gradin_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_wang_tsui_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_gradin_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_wt_gradin_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_wang_tsui_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_gradin_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_wt_gradin_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_wang_tsui_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_wang_tsui_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_gradin_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_gradin_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_wang_tsui_index", entropy_tel)
        self.assertIn("http_retry_jitter_gradin_index", entropy_tel)

    def test_http_retry_jitter_fw_w2_polarization_telemetry(self):
        """Task 253: Test HTTP request retry exponential backoff jitter Foster-Wolfson (FW) & Wolfson II (W2) polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_fw_w2_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_foster_wolfson_ii_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_wolfson_ii_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_fw_w2_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_foster_wolfson_ii_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_wolfson_ii_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_fw_w2_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_foster_wolfson_ii_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_foster_wolfson_ii_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_wolfson_ii_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_wolfson_ii_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_foster_wolfson_ii_index", entropy_tel)
        self.assertIn("http_retry_jitter_wolfson_ii_index", entropy_tel)

    def test_http_retry_jitter_w3_fw3_polarization_telemetry(self):
        """Task 256: Test HTTP request retry exponential backoff jitter Wolfson III (W3) & Foster-Wolfson III (FW3) polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_w3_fw3_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_wolfson_iii_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_foster_wolfson_iii_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_w3_fw3_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_wolfson_iii_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_foster_wolfson_iii_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_w3_fw3_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_wolfson_iii_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_wolfson_iii_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_foster_wolfson_iii_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_foster_wolfson_iii_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_wolfson_iii_index", entropy_tel)
        self.assertIn("http_retry_jitter_foster_wolfson_iii_index", entropy_tel)

    def test_http_retry_jitter_fw4_w4_polarization_telemetry(self):
        """Task 259: Test HTTP request retry exponential backoff jitter Foster-Wolfson IV (FW4) & Wolfson IV (W4) polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_fw4_w4_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_foster_wolfson_iv_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_wolfson_iv_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_fw4_w4_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_foster_wolfson_iv_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_wolfson_iv_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_fw4_w4_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_foster_wolfson_iv_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_foster_wolfson_iv_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_wolfson_iv_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_wolfson_iv_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_foster_wolfson_iv_index", entropy_tel)
        self.assertIn("http_retry_jitter_wolfson_iv_index", entropy_tel)

    def test_http_retry_jitter_w5_fw5_polarization_telemetry(self):
        """Task 262: Test HTTP request retry exponential backoff jitter Wolfson V (W5) & Foster-Wolfson V (FW5) polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_w5_fw5_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_wolfson_v_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_foster_wolfson_v_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_w5_fw5_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_wolfson_v_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_foster_wolfson_v_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_w5_fw5_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_wolfson_v_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_wolfson_v_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_foster_wolfson_v_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_foster_wolfson_v_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_wolfson_v_index", entropy_tel)
        self.assertIn("http_retry_jitter_foster_wolfson_v_index", entropy_tel)

    def test_http_retry_jitter_w6_fw6_polarization_telemetry(self):
        """Task 265: Test HTTP request retry exponential backoff jitter Wolfson VI (W6) & Foster-Wolfson VI (FW6) polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_w6_fw6_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_wolfson_vi_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_foster_wolfson_vi_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_w6_fw6_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_wolfson_vi_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_foster_wolfson_vi_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_w6_fw6_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_wolfson_vi_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_wolfson_vi_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_foster_wolfson_vi_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_foster_wolfson_vi_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_wolfson_vi_index", entropy_tel)
        self.assertIn("http_retry_jitter_foster_wolfson_vi_index", entropy_tel)

    def test_http_retry_jitter_w7_fw7_polarization_telemetry(self):
        """Task 268: Test HTTP request retry exponential backoff jitter Wolfson VII (W7) & Foster-Wolfson VII (FW7) polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_w7_fw7_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_wolfson_vii_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_foster_wolfson_vii_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_w7_fw7_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_wolfson_vii_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_foster_wolfson_vii_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_w7_fw7_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_wolfson_vii_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_wolfson_vii_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_foster_wolfson_vii_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_foster_wolfson_vii_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_wolfson_vii_index", entropy_tel)
        self.assertIn("http_retry_jitter_foster_wolfson_vii_index", entropy_tel)

    def test_http_retry_jitter_w8_fw8_polarization_telemetry(self):
        """Task 271: Test HTTP request retry exponential backoff jitter Wolfson VIII (W8) & Foster-Wolfson VIII (FW8) polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_w8_fw8_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_wolfson_viii_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_foster_wolfson_viii_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_w8_fw8_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_wolfson_viii_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_foster_wolfson_viii_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_w8_fw8_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_wolfson_viii_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_wolfson_viii_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_foster_wolfson_viii_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_foster_wolfson_viii_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_wolfson_viii_index", entropy_tel)
        self.assertIn("http_retry_jitter_foster_wolfson_viii_index", entropy_tel)

    def test_http_retry_jitter_w9_fw9_polarization_telemetry(self):
        """Task 274: Test HTTP request retry exponential backoff jitter Wolfson IX (W9) & Foster-Wolfson IX (FW9) polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_w9_fw9_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_wolfson_ix_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_foster_wolfson_ix_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_w9_fw9_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_wolfson_ix_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_foster_wolfson_ix_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_w9_fw9_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_wolfson_ix_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_wolfson_ix_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_foster_wolfson_ix_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_foster_wolfson_ix_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_wolfson_ix_index", entropy_tel)
        self.assertIn("http_retry_jitter_foster_wolfson_ix_index", entropy_tel)

    def test_http_retry_jitter_w10_fw10_polarization_telemetry(self):
        """Task 277: Test HTTP request retry exponential backoff jitter Wolfson X (W10) & Foster-Wolfson X (FW10) polarization inequality telemetry."""
        empty_tel = self.client.get_http_retry_jitter_w10_fw10_polarization_telemetry()
        self.assertEqual(empty_tel["sample_count"], 0)
        self.assertEqual(empty_tel["http_retry_jitter_wolfson_x_index"], 0.0)
        self.assertEqual(empty_tel["http_retry_jitter_foster_wolfson_x_index"], 0.0)

        # Single sample
        self.client._record_http_retry_jitter(0.02)
        single_tel = self.client.get_http_retry_jitter_w10_fw10_polarization_telemetry()
        self.assertEqual(single_tel["sample_count"], 1)
        self.assertEqual(single_tel["http_retry_jitter_wolfson_x_index"], 0.0)
        self.assertEqual(single_tel["http_retry_jitter_foster_wolfson_x_index"], 0.0)

        # Multiple samples with variance
        for val in [0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50]:
            self.client._record_http_retry_jitter(val)

        tel = self.client.get_http_retry_jitter_w10_fw10_polarization_telemetry()
        self.assertGreater(tel["sample_count"], 1)
        self.assertGreaterEqual(tel["http_retry_jitter_wolfson_x_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_wolfson_x_index"], 1.0)
        self.assertGreaterEqual(tel["http_retry_jitter_foster_wolfson_x_index"], 0.0)
        self.assertLessEqual(tel["http_retry_jitter_foster_wolfson_x_index"], 1.0)

        entropy_tel = self.client.get_http_retry_jitter_entropy_telemetry()
        self.assertIn("http_retry_jitter_wolfson_x_index", entropy_tel)
        self.assertIn("http_retry_jitter_foster_wolfson_x_index", entropy_tel)

if __name__ == '__main__':
    unittest.main()




