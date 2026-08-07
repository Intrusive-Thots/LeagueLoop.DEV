"""
LCU API Handler
Manages communication with the League of Legends Client Update (LCU).
"""
import base64
import math
import random
import sys
import threading
import time
import zlib
from typing import Any, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3
import warnings
import json
import ssl
from websockets.sync.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from utils.logger import Logger
from utils.client_detector import scan_clients


class LCUClient:
    """
    Handles communication with the Local League Client Update (LCU) API.
    Auto-detects the client's lockfile to get port and authentication.
    """

    def __init__(self):
        """Initializes the LCUClient with default values."""
        self._lock = threading.Lock()
        self.port: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.protocol: str = "https"
        self.base_url: Optional[str] = None
        self.is_connected: bool = False
        self.headers: Dict[str, str] = {}
        self.session = requests.Session()
        self.session.verify = False
        
        # 3.2 Connection pooling
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=1)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self._client_pid: Optional[int] = None
        
        # 3.1 & 3.3 State
        self._backoff = 1.0
        self._last_scan_time = 0.0
        
        self._tokens = 20.0
        self._token_capacity = 20.0
        self._token_rate = 5.0
        self._last_token_update = time.time()
        self._rate_lock = threading.Lock()
        
        # 3.5 Offline Retry Queue
        self._offline_queue = []
        self._offline_queue_max = 50  # Item #179: Prevent unbounded growth
        
        # WebSocket internals
        self._subscriptions = {}  # event_name -> list of callbacks
        self._ws_thread = None
        self._ws_should_run = False
        self._ws_connection = None
        self._ws_executor = None

        # Task 127: Automated WS reconnection exponential backoff & jitter
        self._ws_reconnect_backoff = 1.0
        self._ws_max_backoff = 30.0

        # Task 130: Dynamic websocket heartbeat check & stale ping timeout reset
        self._ws_last_msg_timestamp = time.time()
        try:
            from core.constants import LCU_WS_STALE_TIMEOUT_S, LCU_WS_STALE_TIMEOUT_INGAME_S
            self._ws_stale_timeout_s = float(LCU_WS_STALE_TIMEOUT_S)
            self._ws_stale_timeout_ingame_s = float(LCU_WS_STALE_TIMEOUT_INGAME_S)
        except Exception:
            self._ws_stale_timeout_s = 45.0
            self._ws_stale_timeout_ingame_s = 180.0
        self._ws_stale_reset_count = 0
        # When True (match in progress), back off HTTP/WS so we don't thrash the CEF client
        self._in_game_mode: bool = False

        # Task 133: Automated connection drop diagnostics & event loop latency telemetry logging
        self._connection_drop_count = 0
        self._last_drop_reason = ""
        self._drop_history = []
        self._last_connected_timestamp = 0.0
        self._event_loop_latency_ms = 0.0

        # Task 136: Dynamic websocket reconnect rate throttling during network adapter state changes
        self._network_drop_timestamps = []
        self._network_adapter_changes = 0
        self._network_throttle_active = False
        self._network_throttle_backoff_floor = 5.0

        # Telemetry & Anomaly Alerting for WS event latency & throughput
        self._ws_telemetry_lock = threading.RLock()
        self._ws_latency_samples = []
        self._ws_event_count = 0
        self._ws_last_latency_ms = 0.0
        self._ws_event_timestamps = []
        self._ws_start_time = time.time()
        self._ws_anomaly_count = 0
        self._ws_anomaly_threshold_ms = 100.0
        self._ws_burst_alert_active = False

        # Task 145: Automated WS payload compression analysis & memory footprint reporting
        self._ws_total_payload_bytes = 0
        self._ws_last_payload_bytes = 0
        self._ws_max_payload_bytes = 0
        self._ws_compressed_bytes_est = 0
        self._ws_payload_samples = []
        self._ws_last_compression_ratio = 1.0
        self._ws_payload_memory_kb = 0.0

        # Task 148: Automated WS payload deserialization latency profiling
        self._ws_deser_latency_samples = []
        self._ws_last_deser_latency_ms = 0.0
        self._ws_min_deser_latency_ms = float("inf")
        self._ws_max_deser_latency_ms = 0.0
        self._ws_deser_latency_buckets = {
            "<0.1ms": 0,
            "0.1-0.5ms": 0,
            "0.5-1.0ms": 0,
            "1.0-5.0ms": 0,
            ">5.0ms": 0,
        }
        self._ws_deser_count = 0

        # Task 160: Automated websocket JSON deserialization memory pool recycling
        self._ws_deser_pool = []
        self._ws_deser_pool_max_size = 50
        self._ws_deser_recycle_hits = 0
        self._ws_deser_recycle_misses = 0
        self._ws_deser_bytes_recycled = 0

        # Task 163: Dynamic websocket payload decompression memory pool recycling
        self._ws_decomp_pool = []
        self._ws_decomp_pool_max_size = 50
        self._ws_decomp_recycle_hits = 0
        self._ws_decomp_recycle_misses = 0
        self._ws_decomp_bytes_recycled = 0

        # Task 166: Automated websocket compressed payload size ratio anomaly detection
        self._ws_compression_anomaly_count = 0
        self._ws_compression_anomaly_history = []
        self._ws_compression_anomaly_history_max = 50
        self._ws_min_expected_compression_ratio = 0.5
        self._ws_max_expected_compression_ratio = 50.0

        # Task 157: Automated websocket subscription filter performance metrics & dispatch latency telemetry
        self._ws_dispatch_count: int = 0
        self._ws_total_dispatched_callbacks: int = 0
        self._ws_dispatch_total_latency_ms: float = 0.0
        self._ws_max_dispatch_latency_ms: float = 0.0

        # Request Diagnostics & Throttling Metrics
        self._req_diag_lock = threading.Lock()
        self._total_requests_count = 0
        self._rate_limit_throttle_count = 0
        self._total_throttle_sleep_s = 0.0
        self._offline_retry_queued_count = 0
        self._offline_retry_executed_count = 0
        # Task 154: Automated offline request retry queue telemetry & execution success diagnostics
        self._offline_retry_success_count: int = 0
        self._offline_retry_fail_count: int = 0
        self._offline_retry_dropped_count: int = 0
        self._http_429_count = 0
        self._http_5xx_count = 0
        self._http_retry_count = 0
        self._http_max_retries = 3
        self._http_error_count = 0

        # Task 181: Automated HTTP request retry exponential backoff jitter entropy telemetry
        self._http_retry_jitter_samples: list = []
        self._http_retry_jitter_samples_max: int = 200
        self._http_retry_jitter_entropy_bits: float = 0.0
        self._http_retry_jitter_min_s: float = float("inf")
        self._http_retry_jitter_max_s: float = 0.0

        # Task 151: Automated HTTP response status distribution diagnostics & 4xx/5xx error telemetry logging
        self._http_status_codes: Dict[int, int] = {}
        self._http_2xx_count: int = 0
        self._http_3xx_count: int = 0
        self._http_4xx_count: int = 0
        self._recent_http_errors: list = []
        self._max_recent_http_errors: int = 50

        # Task 169: Automated HTTP response status distribution anomaly threshold alerts
        # Use a sliding time window so old lockfile/connect failures stop spamming forever.
        self._http_anomaly_error_rate_threshold_pct: float = 15.0
        self._http_anomaly_5xx_count_threshold: int = 5
        self._http_anomaly_count: int = 0
        self._http_status_anomaly_active: bool = False
        self._http_status_anomaly_history: list = []
        self._http_status_anomaly_history_max: int = 50
        try:
            from core.constants import LCU_HTTP_ANOMALY_WINDOW_S, LCU_HTTP_ANOMALY_LOG_COOLDOWN_S
            self._http_status_window_s = float(LCU_HTTP_ANOMALY_WINDOW_S)
            self._http_anomaly_log_cooldown_s = float(LCU_HTTP_ANOMALY_LOG_COOLDOWN_S)
        except Exception:
            self._http_status_window_s = 120.0
            self._http_anomaly_log_cooldown_s = 60.0
        # (timestamp, is_error, is_5xx) samples for sliding-window error rate
        self._http_status_window: list = []
        self._last_http_anomaly_log_ts: float = 0.0

        # Task 139: Adaptive HTTP client timeout adjustment based on LCU response latency histograms
        self._http_latency_lock = threading.Lock()
        self._http_latency_samples = []
        self._http_latency_buckets = {
            "<10ms": 0,
            "10-50ms": 0,
            "50-100ms": 0,
            "100-200ms": 0,
            "200-500ms": 0,
            ">500ms": 0,
        }
        self._http_min_latency_ms = float("inf")
        self._http_max_latency_ms = 0.0
        self._http_default_timeout_s = 2.0

        # Do NOT connect immediately to avoid blocking UI startup.
        # Connection is handled by the background loop in main.py.

    def set_in_game_mode(self, active: bool) -> None:
        """Enable lighter LCU traffic while League of Legends.exe match is running."""
        active = bool(active)
        if self._in_game_mode == active:
            return
        self._in_game_mode = active
        # Refresh heartbeat so we don't immediately stale-reset on phase enter
        self._ws_last_msg_timestamp = time.time()
        Logger.info(
            "LCU",
            f"In-game mode {'ON' if active else 'OFF'} "
            f"(WS stale timeout={self._effective_ws_stale_timeout():.0f}s)",
        )

    def _effective_ws_stale_timeout(self) -> float:
        if self._in_game_mode:
            return float(self._ws_stale_timeout_ingame_s)
        return float(self._ws_stale_timeout_s)

    def _record_http_latency(self, latency_ms: float) -> None:
        """Records HTTP request latency into sliding window sample array and histogram buckets."""
        with self._http_latency_lock:
            self._http_latency_samples.append(latency_ms)
            if len(self._http_latency_samples) > 200:
                self._http_latency_samples.pop(0)

            if latency_ms < self._http_min_latency_ms:
                self._http_min_latency_ms = latency_ms
            if latency_ms > self._http_max_latency_ms:
                self._http_max_latency_ms = latency_ms

            if latency_ms < 10.0:
                self._http_latency_buckets["<10ms"] += 1
            elif latency_ms < 50.0:
                self._http_latency_buckets["10-50ms"] += 1
            elif latency_ms < 100.0:
                self._http_latency_buckets["50-100ms"] += 1
            elif latency_ms < 200.0:
                self._http_latency_buckets["100-200ms"] += 1
            elif latency_ms < 500.0:
                self._http_latency_buckets["200-500ms"] += 1
            else:
                self._http_latency_buckets[">500ms"] += 1

    def get_adaptive_http_timeout(self) -> float:
        """Calculates dynamic adaptive HTTP timeout based on LCU response latency histograms."""
        with self._http_latency_lock:
            if len(self._http_latency_samples) < 5:
                return self._http_default_timeout_s

            sorted_samples = sorted(self._http_latency_samples)
            idx_95 = int(len(sorted_samples) * 0.95)
            p95_ms = sorted_samples[min(idx_95, len(sorted_samples) - 1)]

            calc_timeout_s = round((p95_ms / 1000.0) * 3.0 + 0.5, 2)
            return max(1.5, min(calc_timeout_s, 8.0))

    def get_http_latency_variance_telemetry(self) -> Dict[str, Any]:
        """Task 172: Returns automated HTTP client request latency variance, standard deviation, and CV telemetry."""
        with self._http_latency_lock:
            samples = self._http_latency_samples.copy()

        if not samples:
            return {
                "http_latency_variance_ms2": 0.0,
                "http_latency_stddev_ms": 0.0,
                "http_latency_cv": 0.0,
                "http_latency_sample_count": 0,
            }

        avg = sum(samples) / len(samples)
        variance = sum((x - avg) ** 2 for x in samples) / len(samples)
        stddev = math.sqrt(variance)
        cv = round(stddev / avg, 4) if avg > 0 else 0.0

        return {
            "http_latency_variance_ms2": round(variance, 4),
            "http_latency_stddev_ms": round(stddev, 4),
            "http_latency_cv": cv,
            "http_latency_sample_count": len(samples),
        }

    def get_http_latency_confidence_interval_telemetry(self, confidence_level: float = 0.95) -> Dict[str, Any]:
        """Task 175: Returns automated HTTP client response latency standard error and confidence interval metrics."""
        with self._http_latency_lock:
            samples = self._http_latency_samples.copy()

        if not samples:
            return {
                "http_latency_mean_ms": 0.0,
                "http_latency_stderr_ms": 0.0,
                "http_latency_ci_margin_ms": 0.0,
                "http_latency_ci_lower_ms": 0.0,
                "http_latency_ci_upper_ms": 0.0,
                "confidence_level": confidence_level,
                "sample_count": 0,
            }

        n = len(samples)
        mean = sum(samples) / n
        if n > 1:
            variance = sum((x - mean) ** 2 for x in samples) / (n - 1)
            stddev = math.sqrt(variance)
            stderr = stddev / math.sqrt(n)
        else:
            variance = 0.0
            stddev = 0.0
            stderr = 0.0

        if confidence_level >= 0.99:
            z = 2.576
        elif confidence_level >= 0.95:
            z = 1.960
        elif confidence_level >= 0.90:
            z = 1.645
        else:
            z = 1.000

        ci_margin = z * stderr
        ci_lower = max(0.0, mean - ci_margin)
        ci_upper = mean + ci_margin

        return {
            "http_latency_mean_ms": round(mean, 4),
            "http_latency_stderr_ms": round(stderr, 4),
            "http_latency_ci_margin_ms": round(ci_margin, 4),
            "http_latency_ci_lower_ms": round(ci_lower, 4),
            "http_latency_ci_upper_ms": round(ci_upper, 4),
            "confidence_level": confidence_level,
            "sample_count": n,
        }

    def get_http_latency_skewness_kurtosis_telemetry(self) -> Dict[str, Any]:
        """Task 178: Returns automated HTTP client request latency skewness & kurtosis statistical telemetry."""
        with self._http_latency_lock:
            samples = self._http_latency_samples.copy()

        if not samples or len(samples) < 3:
            return {
                "http_latency_skewness": 0.0,
                "http_latency_kurtosis": 0.0,
                "http_latency_excess_kurtosis": 0.0,
                "sample_count": len(samples),
            }

        n = len(samples)
        mean = sum(samples) / n
        variance = sum((x - mean) ** 2 for x in samples) / n
        stddev = math.sqrt(variance)

        if stddev < 1e-9:
            return {
                "http_latency_skewness": 0.0,
                "http_latency_kurtosis": 0.0,
                "http_latency_excess_kurtosis": 0.0,
                "sample_count": n,
            }

        m3 = sum((x - mean) ** 3 for x in samples) / n
        m4 = sum((x - mean) ** 4 for x in samples) / n

        skewness = m3 / (stddev ** 3)
        kurtosis = m4 / (stddev ** 4)
        excess_kurtosis = kurtosis - 3.0

        return {
            "http_latency_skewness": round(skewness, 4),
            "http_latency_kurtosis": round(kurtosis, 4),
            "http_latency_excess_kurtosis": round(excess_kurtosis, 4),
            "sample_count": n,
        }

    def _record_http_retry_jitter(self, jitter_s: float) -> None:
        """Task 181: Records HTTP request retry exponential backoff jitter sample and calculates Shannon entropy telemetry."""
        with self._req_diag_lock:
            self._http_retry_jitter_samples.append(jitter_s)
            if len(self._http_retry_jitter_samples) > self._http_retry_jitter_samples_max:
                self._http_retry_jitter_samples.pop(0)

            if jitter_s < self._http_retry_jitter_min_s:
                self._http_retry_jitter_min_s = jitter_s
            if jitter_s > self._http_retry_jitter_max_s:
                self._http_retry_jitter_max_s = jitter_s

            samples = self._http_retry_jitter_samples
            n = len(samples)
            if n < 2:
                self._http_retry_jitter_entropy_bits = 0.0
                return

            buckets = [0] * 10
            for j in samples:
                idx = min(9, max(0, int((j - 0.01) / 0.003)))
                buckets[idx] += 1

            entropy = 0.0
            for count in buckets:
                if count > 0:
                    p = count / n
                    entropy -= p * math.log2(p)

            self._http_retry_jitter_entropy_bits = round(entropy, 4)

    def get_http_retry_jitter_percentiles_telemetry(self) -> Dict[str, Any]:
        """Task 184: Returns automated HTTP request retry exponential backoff jitter distribution percentiles telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples:
            return {
                "http_retry_jitter_p25_s": 0.0,
                "http_retry_jitter_p50_s": 0.0,
                "http_retry_jitter_p75_s": 0.0,
                "http_retry_jitter_p90_s": 0.0,
                "http_retry_jitter_p95_s": 0.0,
                "http_retry_jitter_p99_s": 0.0,
                "http_retry_jitter_iqr_s": 0.0,
                "sample_count": 0,
            }

        sorted_s = sorted(samples)
        n = len(sorted_s)
        p25 = round(sorted_s[int(n * 0.25)], 4)
        p50 = round(sorted_s[int(n * 0.50)], 4)
        p75 = round(sorted_s[min(int(n * 0.75), n - 1)], 4)
        p90 = round(sorted_s[min(int(n * 0.90), n - 1)], 4)
        p95 = round(sorted_s[min(int(n * 0.95), n - 1)], 4)
        p99 = round(sorted_s[min(int(n * 0.99), n - 1)], 4)
        iqr = round(p75 - p25, 4)

        return {
            "http_retry_jitter_p25_s": p25,
            "http_retry_jitter_p50_s": p50,
            "http_retry_jitter_p75_s": p75,
            "http_retry_jitter_p90_s": p90,
            "http_retry_jitter_p95_s": p95,
            "http_retry_jitter_p99_s": p99,
            "http_retry_jitter_iqr_s": iqr,
            "sample_count": n,
        }

    def get_http_retry_jitter_skewness_kurtosis_telemetry(self) -> Dict[str, Any]:
        """Task 187: Returns automated HTTP request retry exponential backoff jitter skewness & kurtosis statistical telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples or len(samples) < 3:
            return {
                "http_retry_jitter_skewness": 0.0,
                "http_retry_jitter_kurtosis": 0.0,
                "http_retry_jitter_excess_kurtosis": 0.0,
                "sample_count": len(samples),
            }

        n = len(samples)
        mean = sum(samples) / n
        variance = sum((x - mean) ** 2 for x in samples) / n
        stddev = math.sqrt(variance)

        if stddev < 1e-9:
            return {
                "http_retry_jitter_skewness": 0.0,
                "http_retry_jitter_kurtosis": 0.0,
                "http_retry_jitter_excess_kurtosis": 0.0,
                "sample_count": n,
            }

        m3 = sum((x - mean) ** 3 for x in samples) / n
        m4 = sum((x - mean) ** 4 for x in samples) / n

        skewness = round(m3 / (stddev ** 3), 4)
        kurtosis = round(m4 / (stddev ** 4), 4)
        excess_kurtosis = round(kurtosis - 3.0, 4)

        return {
            "http_retry_jitter_skewness": skewness,
            "http_retry_jitter_kurtosis": kurtosis,
            "http_retry_jitter_excess_kurtosis": excess_kurtosis,
            "sample_count": n,
        }

    def get_http_retry_jitter_variance_telemetry(self) -> Dict[str, Any]:
        """Task 190: Returns automated HTTP request retry exponential backoff jitter variance & standard deviation telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples or len(samples) < 2:
            return {
                "http_retry_jitter_variance": 0.0,
                "http_retry_jitter_stddev_ms": 0.0,
                "sample_count": len(samples),
            }

        n = len(samples)
        mean = sum(samples) / n
        variance = sum((x - mean) ** 2 for x in samples) / n
        stddev = math.sqrt(variance)

        return {
            "http_retry_jitter_variance": round(variance, 6),
            "http_retry_jitter_stddev_ms": round(stddev * 1000.0, 4),
            "sample_count": n,
        }

    def get_http_retry_jitter_range_telemetry(self) -> Dict[str, Any]:
        """Task 193: Returns automated HTTP request retry exponential backoff jitter range & interquartile range telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples:
            return {
                "http_retry_jitter_min_ms": 0.0,
                "http_retry_jitter_max_ms": 0.0,
                "http_retry_jitter_range_ms": 0.0,
                "http_retry_jitter_iqr_ms": 0.0,
                "sample_count": 0,
            }

        sorted_s = sorted(samples)
        n = len(sorted_s)
        min_s = sorted_s[0]
        max_s = sorted_s[-1]
        range_s = max_s - min_s

        p25_s = sorted_s[int(n * 0.25)]
        p75_s = sorted_s[min(int(n * 0.75), n - 1)]
        iqr_s = p75_s - p25_s

        return {
            "http_retry_jitter_min_ms": round(min_s * 1000.0, 4),
            "http_retry_jitter_max_ms": round(max_s * 1000.0, 4),
            "http_retry_jitter_range_ms": round(range_s * 1000.0, 4),
            "http_retry_jitter_iqr_ms": round(iqr_s * 1000.0, 4),
            "sample_count": n,
        }

    def get_http_retry_jitter_confidence_interval_telemetry(self, confidence_level: float = 0.95) -> Dict[str, Any]:
        """Task 196: Returns automated HTTP request retry exponential backoff jitter confidence interval telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples or len(samples) < 2:
            return {
                "http_retry_jitter_mean_ms": 0.0,
                "http_retry_jitter_stderr_ms": 0.0,
                "http_retry_jitter_ci_margin_ms": 0.0,
                "http_retry_jitter_ci95_lower_ms": 0.0,
                "http_retry_jitter_ci95_upper_ms": 0.0,
                "confidence_level": confidence_level,
                "sample_count": len(samples),
            }

        n = len(samples)
        mean_s = sum(samples) / n
        variance = sum((x - mean_s) ** 2 for x in samples) / (n - 1)
        stddev_s = math.sqrt(variance)
        stderr_s = stddev_s / math.sqrt(n)

        if confidence_level >= 0.99:
            z = 2.576
        elif confidence_level >= 0.95:
            z = 1.960
        elif confidence_level >= 0.90:
            z = 1.645
        else:
            z = 1.000

        ci_margin_s = z * stderr_s
        mean_ms = mean_s * 1000.0
        stderr_ms = stderr_s * 1000.0
        ci_margin_ms = ci_margin_s * 1000.0
        ci_lower_ms = max(0.0, mean_ms - ci_margin_ms)
        ci_upper_ms = mean_ms + ci_margin_ms

        return {
            "http_retry_jitter_mean_ms": round(mean_ms, 4),
            "http_retry_jitter_stderr_ms": round(stderr_ms, 4),
            "http_retry_jitter_ci_margin_ms": round(ci_margin_ms, 4),
            "http_retry_jitter_ci95_lower_ms": round(ci_lower_ms, 4),
            "http_retry_jitter_ci95_upper_ms": round(ci_upper_ms, 4),
            "confidence_level": confidence_level,
            "sample_count": n,
        }

    def get_http_retry_jitter_margin_of_error_telemetry(self, confidence_level: float = 0.95) -> Dict[str, Any]:
        """Task 199: Returns automated HTTP request retry exponential backoff jitter margin of error percentiles telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples or len(samples) < 2:
            return {
                "http_retry_jitter_moe_ms": 0.0,
                "http_retry_jitter_relative_moe_pct": 0.0,
                "confidence_level": confidence_level,
                "sample_count": len(samples),
            }

        n = len(samples)
        mean_s = sum(samples) / n
        variance = sum((x - mean_s) ** 2 for x in samples) / (n - 1)
        stddev_s = math.sqrt(variance)
        stderr_s = stddev_s / math.sqrt(n)

        if confidence_level >= 0.99:
            z = 2.576
        elif confidence_level >= 0.95:
            z = 1.960
        elif confidence_level >= 0.90:
            z = 1.645
        else:
            z = 1.000

        moe_s = z * stderr_s
        moe_ms = moe_s * 1000.0
        rel_moe = round((moe_s / mean_s) * 100.0, 4) if mean_s > 0 else 0.0

        return {
            "http_retry_jitter_moe_ms": round(moe_ms, 4),
            "http_retry_jitter_relative_moe_pct": rel_moe,
            "confidence_level": confidence_level,
            "sample_count": n,
        }

    def get_http_retry_jitter_geometric_harmonic_means_telemetry(self) -> Dict[str, Any]:
        """Task 202: Returns automated HTTP request retry exponential backoff jitter geometric mean & harmonic mean telemetry."""
        with self._req_diag_lock:
            samples = [x for x in self._http_retry_jitter_samples if x > 0]

        if not samples:
            return {
                "http_retry_jitter_geometric_mean_s": 0.0,
                "http_retry_jitter_harmonic_mean_s": 0.0,
                "sample_count": 0,
            }

        n = len(samples)
        log_sum = sum(math.log(x) for x in samples)
        geo_mean = math.exp(log_sum / n)

        recip_sum = sum(1.0 / x for x in samples)
        harm_mean = n / recip_sum if recip_sum > 0 else 0.0

        return {
            "http_retry_jitter_geometric_mean_s": round(geo_mean, 6),
            "http_retry_jitter_harmonic_mean_s": round(harm_mean, 6),
            "sample_count": n,
        }

    def get_http_retry_jitter_skewness_kurtosis_ci_telemetry(self, confidence_level: float = 0.95) -> Dict[str, Any]:
        """Task 205: Returns automated HTTP request retry exponential backoff jitter skewness & kurtosis confidence interval telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples or len(samples) < 4:
            return {
                "http_retry_jitter_skewness_stderr": 0.0,
                "http_retry_jitter_skewness_ci_margin": 0.0,
                "http_retry_jitter_skewness_ci95_lower": 0.0,
                "http_retry_jitter_skewness_ci95_upper": 0.0,
                "http_retry_jitter_kurtosis_stderr": 0.0,
                "http_retry_jitter_kurtosis_ci_margin": 0.0,
                "http_retry_jitter_kurtosis_ci95_lower": 0.0,
                "http_retry_jitter_kurtosis_ci95_upper": 0.0,
                "confidence_level": confidence_level,
                "sample_count": len(samples),
            }

        n = len(samples)
        skew_stderr = math.sqrt(6.0 / n)
        kurt_stderr = math.sqrt(24.0 / n)

        if confidence_level >= 0.99:
            z = 2.576
        elif confidence_level >= 0.95:
            z = 1.960
        elif confidence_level >= 0.90:
            z = 1.645
        else:
            z = 1.000

        skew_margin = z * skew_stderr
        kurt_margin = z * kurt_stderr

        shape_meta = self.get_http_retry_jitter_skewness_kurtosis_telemetry()
        skew = shape_meta.get("http_retry_jitter_skewness", 0.0)
        kurt = shape_meta.get("http_retry_jitter_kurtosis", 0.0)

        return {
            "http_retry_jitter_skewness_stderr": round(skew_stderr, 4),
            "http_retry_jitter_skewness_ci_margin": round(skew_margin, 4),
            "http_retry_jitter_skewness_ci95_lower": round(skew - skew_margin, 4),
            "http_retry_jitter_skewness_ci95_upper": round(skew + skew_margin, 4),
            "http_retry_jitter_kurtosis_stderr": round(kurt_stderr, 4),
            "http_retry_jitter_kurtosis_ci_margin": round(kurt_margin, 4),
            "http_retry_jitter_kurtosis_ci95_lower": round(kurt - kurt_margin, 4),
            "http_retry_jitter_kurtosis_ci95_upper": round(kurt + kurt_margin, 4),
            "confidence_level": confidence_level,
            "sample_count": n,
        }

    def get_http_retry_jitter_rse_variance_ratio_telemetry(self) -> Dict[str, Any]:
        """Task 208: Returns automated HTTP request retry exponential backoff jitter relative standard error & variance ratio telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples or len(samples) < 2:
            return {
                "http_retry_jitter_rse_pct": 0.0,
                "http_retry_jitter_variance_ratio": 0.0,
                "http_retry_jitter_signal_to_noise_ratio": 0.0,
                "sample_count": len(samples),
            }

        n = len(samples)
        mean_s = sum(samples) / n
        if mean_s == 0:
            return {
                "http_retry_jitter_rse_pct": 0.0,
                "http_retry_jitter_variance_ratio": 0.0,
                "http_retry_jitter_signal_to_noise_ratio": 0.0,
                "sample_count": n,
            }

        variance_s = sum((x - mean_s) ** 2 for x in samples) / (n - 1)
        stddev_s = math.sqrt(variance_s)
        stderr_s = stddev_s / math.sqrt(n)

        rse_pct = (stderr_s / mean_s) * 100.0
        var_ratio = variance_s / mean_s
        snr = mean_s / stddev_s if stddev_s > 0 else 0.0

        return {
            "http_retry_jitter_rse_pct": round(rse_pct, 4),
            "http_retry_jitter_variance_ratio": round(var_ratio, 6),
            "http_retry_jitter_signal_to_noise_ratio": round(snr, 4),
            "sample_count": n,
        }

    def get_http_retry_jitter_cv_fano_ci_telemetry(self, confidence_level: float = 0.95) -> Dict[str, Any]:
        """Task 211: Returns automated HTTP request retry exponential backoff jitter coefficient of variation & Fano factor confidence interval telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples or len(samples) < 2:
            return {
                "http_retry_jitter_cv": 0.0,
                "http_retry_jitter_cv_stderr": 0.0,
                "http_retry_jitter_cv_ci_margin": 0.0,
                "http_retry_jitter_cv_ci_lower": 0.0,
                "http_retry_jitter_cv_ci_upper": 0.0,
                "http_retry_jitter_fano": 0.0,
                "http_retry_jitter_fano_stderr": 0.0,
                "http_retry_jitter_fano_ci_margin": 0.0,
                "http_retry_jitter_fano_ci_lower": 0.0,
                "http_retry_jitter_fano_ci_upper": 0.0,
                "confidence_level": confidence_level,
                "sample_count": len(samples),
            }

        n = len(samples)
        mean_s = sum(samples) / n
        if mean_s == 0:
            return {
                "http_retry_jitter_cv": 0.0,
                "http_retry_jitter_cv_stderr": 0.0,
                "http_retry_jitter_cv_ci_margin": 0.0,
                "http_retry_jitter_cv_ci_lower": 0.0,
                "http_retry_jitter_cv_ci_upper": 0.0,
                "http_retry_jitter_fano": 0.0,
                "http_retry_jitter_fano_stderr": 0.0,
                "http_retry_jitter_fano_ci_margin": 0.0,
                "http_retry_jitter_fano_ci_lower": 0.0,
                "http_retry_jitter_fano_ci_upper": 0.0,
                "confidence_level": confidence_level,
                "sample_count": n,
            }

        variance_s = sum((x - mean_s) ** 2 for x in samples) / (n - 1)
        stddev_s = math.sqrt(variance_s)

        cv = stddev_s / mean_s
        cv_stderr = (cv / math.sqrt(2 * n)) * math.sqrt(1 + 2 * (cv ** 2))

        fano = variance_s / mean_s
        fano_stderr = fano * math.sqrt(2.0 / (n - 1))

        if confidence_level >= 0.99:
            z = 2.576
        elif confidence_level >= 0.95:
            z = 1.960
        elif confidence_level >= 0.90:
            z = 1.645
        else:
            z = 1.000

        cv_margin = z * cv_stderr
        cv_ci_lower = max(0.0, cv - cv_margin)
        cv_ci_upper = cv + cv_margin

        fano_margin = z * fano_stderr
        fano_ci_lower = max(0.0, fano - fano_margin)
        fano_ci_upper = fano + fano_margin

        return {
            "http_retry_jitter_cv": round(cv, 4),
            "http_retry_jitter_cv_stderr": round(cv_stderr, 4),
            "http_retry_jitter_cv_ci_margin": round(cv_margin, 4),
            "http_retry_jitter_cv_ci_lower": round(cv_ci_lower, 4),
            "http_retry_jitter_cv_ci_upper": round(cv_ci_upper, 4),
            "http_retry_jitter_fano": round(fano, 4),
            "http_retry_jitter_fano_stderr": round(fano_stderr, 4),
            "http_retry_jitter_fano_ci_margin": round(fano_margin, 4),
            "http_retry_jitter_fano_ci_lower": round(fano_ci_lower, 4),
            "http_retry_jitter_fano_ci_upper": round(fano_ci_upper, 4),
            "confidence_level": confidence_level,
            "sample_count": n,
        }

    def get_http_retry_jitter_mad_telemetry(self) -> Dict[str, Any]:
        """Task 214: Returns automated HTTP request retry exponential backoff jitter mean absolute deviation & median absolute deviation telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples:
            return {
                "http_retry_jitter_mad_s": 0.0,
                "http_retry_jitter_mad_ms": 0.0,
                "http_retry_jitter_relative_mad_pct": 0.0,
                "http_retry_jitter_medad_s": 0.0,
                "http_retry_jitter_medad_ms": 0.0,
                "http_retry_jitter_normal_scaled_medad_s": 0.0,
                "sample_count": 0,
            }

        n = len(samples)
        mean_s = sum(samples) / n
        mad_s = sum(abs(x - mean_s) for x in samples) / n
        rel_mad_pct = (mad_s / mean_s * 100.0) if mean_s > 0 else 0.0

        sorted_s = sorted(samples)
        if n % 2 == 1:
            median_s = sorted_s[n // 2]
        else:
            median_s = (sorted_s[n // 2 - 1] + sorted_s[n // 2]) / 2.0

        abs_devs = sorted([abs(x - median_s) for x in samples])
        dev_n = len(abs_devs)
        if dev_n % 2 == 1:
            medad_s = abs_devs[dev_n // 2]
        else:
            medad_s = (abs_devs[dev_n // 2 - 1] + abs_devs[dev_n // 2]) / 2.0

        scaled_medad_s = 1.4826 * medad_s

        return {
            "http_retry_jitter_mad_s": round(mad_s, 6),
            "http_retry_jitter_mad_ms": round(mad_s * 1000.0, 4),
            "http_retry_jitter_relative_mad_pct": round(rel_mad_pct, 4),
            "http_retry_jitter_medad_s": round(medad_s, 6),
            "http_retry_jitter_medad_ms": round(medad_s * 1000.0, 4),
            "http_retry_jitter_normal_scaled_medad_s": round(scaled_medad_s, 6),
            "sample_count": n,
        }

    def get_http_retry_jitter_gini_hoover_telemetry(self) -> Dict[str, Any]:
        """Task 217: Returns automated HTTP request retry exponential backoff jitter Gini coefficient & Hoover index inequality telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples:
            return {
                "http_retry_jitter_gini_coefficient": 0.0,
                "http_retry_jitter_hoover_index": 0.0,
                "http_retry_jitter_relative_mean_difference": 0.0,
                "sample_count": 0,
            }

        n = len(samples)
        mean_s = sum(samples) / n
        if mean_s == 0:
            return {
                "http_retry_jitter_gini_coefficient": 0.0,
                "http_retry_jitter_hoover_index": 0.0,
                "http_retry_jitter_relative_mean_difference": 0.0,
                "sample_count": n,
            }

        sorted_s = sorted(samples)
        sum_i_x = sum((i + 1) * val for i, val in enumerate(sorted_s))
        total_sum = sum(sorted_s)
        gini = (2.0 * sum_i_x / (n * total_sum)) - ((n + 1.0) / n)
        gini = max(0.0, gini)

        mad_sum = sum(abs(x - mean_s) for x in samples)
        hoover = mad_sum / (2.0 * total_sum)
        rel_mean_diff = 2.0 * gini

        return {
            "http_retry_jitter_gini_coefficient": round(gini, 4),
            "http_retry_jitter_hoover_index": round(hoover, 4),
            "http_retry_jitter_relative_mean_difference": round(rel_mean_diff, 4),
            "sample_count": n,
        }

    def get_http_retry_jitter_theil_atkinson_telemetry(self) -> Dict[str, Any]:
        """Task 220: Returns automated HTTP request retry exponential backoff jitter Theil index & Atkinson index inequality telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()

        if not samples:
            return {
                "http_retry_jitter_theil_index": 0.0,
                "http_retry_jitter_atkinson_index": 0.0,
                "sample_count": 0,
            }

        n = len(samples)
        mean_s = sum(samples) / n
        if mean_s == 0:
            return {
                "http_retry_jitter_theil_index": 0.0,
                "http_retry_jitter_atkinson_index": 0.0,
                "sample_count": n,
            }

        theil_sum = 0.0
        for x in samples:
            if x > 0:
                ratio = x / mean_s
                theil_sum += ratio * math.log(ratio)
        theil_index = max(0.0, theil_sum / n)

        sqrt_sum = sum(math.sqrt(max(0.0, x)) for x in samples)
        atkinson_mean = (sqrt_sum / n) ** 2
        atkinson_index = max(0.0, min(1.0, 1.0 - (atkinson_mean / mean_s)))

        return {
            "http_retry_jitter_theil_index": round(theil_index, 4),
            "http_retry_jitter_atkinson_index": round(atkinson_index, 4),
            "sample_count": n,
        }

    def get_http_retry_jitter_entropy_telemetry(self) -> Dict[str, Any]:
        """Task 181, 184, 187, 190, 193, 196, 199, 202, 205, 208, 211, 214, 217 & 220: Returns automated HTTP request retry exponential backoff jitter entropy, percentiles, skewness, kurtosis, variance, standard deviation, range, confidence interval, margin of error, geometric mean, harmonic mean, skewness/kurtosis CI, relative standard error/variance ratio, CV/Fano factor CI, MAD/MedAD, Gini/Hoover inequality, and Theil/Atkinson inequality telemetry."""
        with self._req_diag_lock:
            samples = self._http_retry_jitter_samples.copy()
            entropy = self._http_retry_jitter_entropy_bits
            min_s = round(self._http_retry_jitter_min_s, 4) if self._http_retry_jitter_min_s != float("inf") else 0.0
            max_s = round(self._http_retry_jitter_max_s, 4)
            retries = self._http_retry_count

        avg_s = round(sum(samples) / len(samples), 4) if samples else 0.0
        perc_meta = self.get_http_retry_jitter_percentiles_telemetry()
        shape_meta = self.get_http_retry_jitter_skewness_kurtosis_telemetry()
        var_meta = self.get_http_retry_jitter_variance_telemetry()
        range_meta = self.get_http_retry_jitter_range_telemetry()
        ci_meta = self.get_http_retry_jitter_confidence_interval_telemetry()
        moe_meta = self.get_http_retry_jitter_margin_of_error_telemetry()
        geo_harm_meta = self.get_http_retry_jitter_geometric_harmonic_means_telemetry()
        skew_kurt_ci_meta = self.get_http_retry_jitter_skewness_kurtosis_ci_telemetry()
        rse_var_ratio_meta = self.get_http_retry_jitter_rse_variance_ratio_telemetry()
        cv_fano_ci_meta = self.get_http_retry_jitter_cv_fano_ci_telemetry()
        mad_meta = self.get_http_retry_jitter_mad_telemetry()
        gini_hoover_meta = self.get_http_retry_jitter_gini_hoover_telemetry()
        theil_atkinson_meta = self.get_http_retry_jitter_theil_atkinson_telemetry()

        res = {
            "http_retry_jitter_samples_count": len(samples),
            "http_retry_jitter_entropy_bits": entropy,
            "http_retry_jitter_min_s": min_s,
            "http_retry_jitter_max_s": max_s,
            "http_retry_jitter_avg_s": avg_s,
            "http_retry_count": retries,
        }
        res.update(perc_meta)
        res.update(shape_meta)
        res.update(var_meta)
        res.update(range_meta)
        res.update(ci_meta)
        res.update(moe_meta)
        res.update(geo_harm_meta)
        res.update(skew_kurt_ci_meta)
        res.update(rse_var_ratio_meta)
        res.update(cv_fano_ci_meta)
        res.update(mad_meta)
        res.update(gini_hoover_meta)
        res.update(theil_atkinson_meta)
        return res

    def get_http_latency_histogram(self) -> Dict[str, Any]:
        """Task 172, 175 & 178: Returns LCU response latency histogram buckets, variance metrics, confidence intervals, and skewness/kurtosis statistics."""
        with self._http_latency_lock:
            samples = self._http_latency_samples.copy()
            buckets = self._http_latency_buckets.copy()
            min_ms = self._http_min_latency_ms if self._http_min_latency_ms != float("inf") else 0.0
            max_ms = self._http_max_latency_ms

        if samples:
            sorted_s = sorted(samples)
            p50 = sorted_s[int(len(sorted_s) * 0.50)]
            p95 = sorted_s[min(int(len(sorted_s) * 0.95), len(sorted_s) - 1)]
            p99 = sorted_s[min(int(len(sorted_s) * 0.99), len(sorted_s) - 1)]
            avg = sum(samples) / len(samples)
        else:
            p50 = p95 = p99 = avg = 0.0

        adaptive_timeout = self.get_adaptive_http_timeout()
        var_meta = self.get_http_latency_variance_telemetry()
        ci_meta = self.get_http_latency_confidence_interval_telemetry()
        shape_meta = self.get_http_latency_skewness_kurtosis_telemetry()

        res = {
            "sample_count": len(samples),
            "buckets": buckets,
            "min_latency_ms": round(min_ms, 2),
            "max_latency_ms": round(max_ms, 2),
            "avg_latency_ms": round(avg, 2),
            "p50_latency_ms": round(p50, 2),
            "p95_latency_ms": round(p95, 2),
            "p99_latency_ms": round(p99, 2),
            "adaptive_timeout_s": adaptive_timeout,
        }
        res.update(var_meta)
        res.update(ci_meta)
        res.update(shape_meta)
        return res

    def connect(self, silent=False) -> bool:
        """Attempts to read the lockfile and establish connection details."""
        with self._lock:
            # Atomic check: If we connected while waiting for lock, return success
            if self.is_connected:
                return True

            try:
                # Check connection throttling and sleep/wake gaps
                now = time.time()
                if self._last_scan_time > 0 and (now - self._last_scan_time) > 15.0:
                    Logger.info("LCU", "System sleep/wake gap detected (>15s). Resetting backoff strategy.")
                    self._backoff = 1.0
                    self._last_scan_time = 0.0
                    try:
                        from core.events import EventBus
                        EventBus.emit("lcu_sleep_wake_recovery", True)
                    except Exception:
                        pass

                if now - self._last_scan_time < self._backoff:
                    return False
                self._last_scan_time = now

                # Use unified client scanner
                clients = scan_clients()
                league_info = clients.get("league", {})
                
                if not league_info.get("connected"):
                    if not silent:
                        Logger.debug("LCU", "League Client not found or not connected.")
                    if self.is_connected:
                        from core.events import EventBus
                        EventBus.emit("lcu_connected", False)
                    self.is_connected = False
                    self._backoff = min(self._backoff * 1.2, 2.0)
                    return False

                self.port = league_info["port"]
                self.auth_token = league_info["token"]
                self._client_pid = league_info["pid"]

                if self.port and self.auth_token:
                    auth_str = f"riot:{self.auth_token}"
                    b64_auth = base64.b64encode(auth_str.encode()).decode()
                    self.headers = {
                        "Authorization": f"Basic {b64_auth}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    }
                    self.session.headers.update(self.headers)
                    self.base_url = f"https://127.0.0.1:{self.port}"
                    self.is_connected = True
                    self._last_connected_timestamp = time.time()
                    self._backoff = 1.0  # Reset backoff on success
                    from core.events import EventBus
                    EventBus.emit("lcu_connected", True)
                    Logger.debug("LCU", f"Connected to port {self.port}")
                    return True

                Logger.debug("LCU", "Found League Client but credentials are missing.")

            except Exception as e:
                Logger.error("LCU", f"Connection Error: {e}")
                if self.is_connected:
                    from core.events import EventBus
                    EventBus.emit("lcu_connected", False)
                self.is_connected = False

            return False

    def reset_sleep_wake_backoff(self) -> None:
        """Resets reconnection backoff and scanning throttle after system sleep or wake events."""
        with self._lock:
            self._backoff = 1.0
            self._last_scan_time = 0.0
            Logger.info("LCU", "Sleep/wake backoff reset executed.")
            try:
                from core.events import EventBus
                EventBus.emit("lcu_sleep_wake_recovery", True)
            except Exception:
                pass

    def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        silent: bool = False,
    ) -> Optional[requests.Response]:
        """Generic wrapper for LCU requests."""
        if not self.is_connected:
            if not self.connect(silent=silent):
                if method in ["POST", "PUT", "PATCH", "DELETE"]:
                    # 3.5 Offline Retry Queue: save state mutations for when we reconnect
                    # Item #179: Cap queue size to prevent unbounded growth
                    if len(self._offline_queue) < self._offline_queue_max:
                        self._offline_queue.append((method, endpoint, data))
                        with self._req_diag_lock:
                            self._offline_retry_queued_count += 1
                    else:
                        with self._req_diag_lock:
                            self._offline_retry_dropped_count += 1
                return None

        # Flush 3.5 Offline Retry Queue on successful connection
        with self._lock:
            oq = self._offline_queue.copy()
            self._offline_queue.clear()
        if oq:
            with self._req_diag_lock:
                self._offline_retry_executed_count += len(oq)
            # Item #177: Use bounded executor instead of spawning raw threads
            for m, e, d in oq:
                if self._ws_executor:
                    self._ws_executor.submit(self._execute_offline_retry, m, e, d)
                else:
                    t = threading.Thread(target=self._execute_offline_retry, args=(m, e, d), daemon=True)
                    t.start()

        # 3.3 Strict Token Bucket Rate-Limiter
        # Item #178: Calculate sleep time inside lock, but sleep outside to prevent deadlock
        sleep_time = 0.0
        with self._rate_lock:
            now = time.time()
            self._tokens = min(self._token_capacity, self._tokens + (now - self._last_token_update) * self._token_rate)
            self._last_token_update = now
            if self._tokens < 1.0:
                sleep_time = (1.0 - self._tokens) / self._token_rate
                self._tokens = 0.0
                self._last_token_update = time.time()
            else:
                self._tokens -= 1.0
        if sleep_time > 0:
            with self._req_diag_lock:
                self._rate_limit_throttle_count += 1
                self._total_throttle_sleep_s += sleep_time
            time.sleep(sleep_time)

        with self._req_diag_lock:
            self._total_requests_count += 1

        url = f"{self.base_url}{endpoint}"
        t_start = time.time()
        max_attempts = self._http_max_retries

        for attempt in range(max_attempts):
            try:
                if not silent and attempt == 0:
                    Logger.debug("LCU", f"REQ -> {method} {endpoint}")
                
                # TRACE payload format
                if endpoint == "/lol-lobby/v2/lobby" and method == "POST":
                    Logger.debug("LCU_TRACE", f"DATA TYPE: {type(data)} | RAW: {data}")
                    
                adaptive_timeout = self.get_adaptive_http_timeout()
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
                    response = self.session.request(
                        method=method,
                        url=url,
                        json=data,
                        verify=False,
                        timeout=adaptive_timeout,
                    )

                dur = time.time() - t_start
                self._record_http_latency(dur * 1000.0)
                self._record_http_status_code(response.status_code, method, endpoint)

                if response.status_code == 429:
                    if not silent:
                        Logger.warning("LCU", f"HTTP 429 Rate Limit response on {endpoint}")
                elif 500 <= response.status_code <= 599:
                    if attempt < max_attempts - 1:
                        with self._req_diag_lock:
                            self._http_retry_count += 1
                        base_delay = 0.05 * (2 ** attempt)
                        jitter = random.uniform(0.01, 0.04)
                        self._record_http_retry_jitter(jitter)
                        retry_delay = base_delay + jitter
                        if not silent:
                            Logger.warning("LCU", f"HTTP {response.status_code} Transient Server Error on {endpoint}. Retrying attempt {attempt + 1}/{max_attempts} after {retry_delay:.3f}s jitter backoff...")
                        time.sleep(retry_delay)
                        continue

                if not silent:
                    Logger.debug(
                        "LCU", f"RES <- {response.status_code} [{dur:.3f}s] {endpoint}"
                    )
                return response
            except requests.exceptions.ConnectionError:
                dur = time.time() - t_start
                self._record_http_latency(dur * 1000.0)
                self._record_http_transport_failure(method, endpoint, "connection")
                # Expected when the game is closed or restarting
                self.is_connected = False
                return None
            except requests.exceptions.ReadTimeout:
                # Expected for long-polling endpoints — do not treat as hard error spam
                dur = time.time() - t_start
                self._record_http_latency(dur * 1000.0)
                return None
            except requests.RequestException as e:
                dur = time.time() - t_start
                self._record_http_latency(dur * 1000.0)
                self._record_http_transport_failure(method, endpoint, "request")
                Logger.error("LCU", f"FAIL [{dur:.3f}s] {endpoint} : {e}")
                # Connection lost?
                self.is_connected = False
                return None

        return None

    def _record_http_status_code(self, status_code: int, method: str, endpoint: str) -> None:
        """Task 151 & 169: Records HTTP status codes; anomaly alerts use a sliding window (no 200 spam)."""
        is_error = status_code >= 400
        with self._req_diag_lock:
            self._http_status_codes[status_code] = self._http_status_codes.get(status_code, 0) + 1
            if 200 <= status_code <= 299:
                self._http_2xx_count += 1
            elif 300 <= status_code <= 399:
                self._http_3xx_count += 1
            elif 400 <= status_code <= 499:
                self._http_4xx_count += 1
                if status_code == 429:
                    self._http_429_count += 1
            elif 500 <= status_code <= 599:
                self._http_5xx_count += 1

            if is_error:
                err_entry = {
                    "timestamp": time.time(),
                    "method": method,
                    "endpoint": endpoint,
                    "status_code": status_code,
                }
                self._recent_http_errors.append(err_entry)
                if len(self._recent_http_errors) > self._max_recent_http_errors:
                    self._recent_http_errors.pop(0)
                Logger.warning("LCU_TELEMETRY", f"HTTP {status_code} Error on {method} {endpoint}")

            self._evaluate_http_status_anomaly(
                is_error=is_error,
                status_code=status_code,
                method=method,
                endpoint=endpoint,
            )

    def _record_http_transport_failure(self, method: str, endpoint: str, reason: str = "transport") -> None:
        """Count connection/timeout failures in the sliding anomaly window without a status code."""
        with self._req_diag_lock:
            self._http_error_count += 1
            self._evaluate_http_status_anomaly(
                is_error=True,
                status_code=0,
                method=method,
                endpoint=endpoint,
                reason_override=f"Transport failure ({reason})",
            )

    def _evaluate_http_status_anomaly(
        self,
        is_error: bool,
        status_code: int,
        method: str,
        endpoint: str,
        reason_override: Optional[str] = None,
    ) -> None:
        """Sliding-window error-rate alerts. Never alert solely because a 200 followed old failures."""
        # Caller must hold _req_diag_lock
        now = time.time()
        is_5xx_sample = status_code >= 500
        self._http_status_window.append((now, is_error, is_5xx_sample))
        cutoff = now - self._http_status_window_s
        self._http_status_window = [s for s in self._http_status_window if s[0] >= cutoff]

        window_total = len(self._http_status_window)
        window_errs = sum(1 for _, err, _ in self._http_status_window if err)
        window_5xx = sum(1 for _, _, is5 in self._http_status_window if is5)
        err_rate = round((window_errs / max(1, window_total)) * 100.0, 2)

        is_rate_anomaly = window_total >= 10 and err_rate > self._http_anomaly_error_rate_threshold_pct
        is_5xx_anomaly = window_5xx >= self._http_anomaly_5xx_count_threshold

        # Only raise on a real failing sample, never on successful 2xx/3xx
        hard_fail = status_code >= 500 or (status_code == 0 and is_error)
        should_alert = hard_fail or (is_error and (is_rate_anomaly or is_5xx_anomaly))

        if should_alert:
            was_active = self._http_status_anomaly_active
            self._http_status_anomaly_active = True
            self._http_anomaly_count += 1
            if reason_override:
                reason = reason_override
            elif is_rate_anomaly:
                reason = (
                    f"Sliding-window error rate {err_rate}% exceeded threshold "
                    f"{self._http_anomaly_error_rate_threshold_pct}% "
                    f"({window_errs}/{window_total} in {self._http_status_window_s:.0f}s)"
                )
            else:
                reason = f"HTTP 5xx count {window_5xx} reached threshold"

            anomaly_entry = {
                "timestamp": now,
                "status_code": status_code,
                "method": method,
                "endpoint": endpoint,
                "error_rate_pct": err_rate,
                "reason": reason,
            }
            self._http_status_anomaly_history.append(anomaly_entry)
            if len(self._http_status_anomaly_history) > self._http_status_anomaly_history_max:
                self._http_status_anomaly_history.pop(0)

            # Log once on transition, or at most once per cooldown while active
            if (not was_active) or (now - self._last_http_anomaly_log_ts >= self._http_anomaly_log_cooldown_s):
                self._last_http_anomaly_log_ts = now
                Logger.warning(
                    "LCU_HTTP_STATUS_ANOMALY",
                    f"HTTP status anomaly on {method} {endpoint} (status {status_code}): {reason}",
                )
        else:
            # Recover as soon as the sliding window looks healthy (successes dilute old failures)
            if not is_rate_anomaly:
                self._http_status_anomaly_active = False

    def get_http_status_anomaly_telemetry(self) -> Dict[str, Any]:
        """Task 169: Returns automated HTTP response status distribution anomaly threshold alert telemetry."""
        with self._req_diag_lock:
            anomalies = self._http_anomaly_count
            active = self._http_status_anomaly_active
            history = [dict(entry) for entry in self._http_status_anomaly_history]
            last_anomaly = dict(history[-1]) if history else None
            err_thresh = self._http_anomaly_error_rate_threshold_pct
            c5xx_thresh = self._http_anomaly_5xx_count_threshold

        return {
            "http_status_anomaly_count": anomalies,
            "http_status_anomaly_active": active,
            "http_anomaly_error_rate_threshold_pct": err_thresh,
            "http_anomaly_5xx_count_threshold": c5xx_thresh,
            "last_http_status_anomaly": last_anomaly,
            "recent_http_status_anomalies": history,
        }

    def get_http_status_telemetry(self) -> Dict[str, Any]:
        """Task 151 & 169: Returns automated HTTP response status distribution diagnostics & error anomaly telemetry."""
        with self._req_diag_lock:
            dist = {str(k): v for k, v in sorted(self._http_status_codes.items())}
            total_reqs = self._total_requests_count
            err_count = self._http_4xx_count + self._http_5xx_count + self._http_error_count
            err_rate = round((err_count / max(1, total_reqs)) * 100.0, 2)
            recent_errs = list(self._recent_http_errors)

        anomaly_meta = self.get_http_status_anomaly_telemetry()

        res = {
            "total_requests": total_reqs,
            "status_code_distribution": dist,
            "http_2xx_count": self._http_2xx_count,
            "http_3xx_count": self._http_3xx_count,
            "http_4xx_count": self._http_4xx_count,
            "http_5xx_count": self._http_5xx_count,
            "http_429_count": self._http_429_count,
            "http_error_count": self._http_error_count,
            "http_error_rate_pct": err_rate,
            "recent_errors_count": len(recent_errs),
            "recent_errors": recent_errs,
        }
        res.update(anomaly_meta)
        return res

    def _execute_offline_retry(self, method: str, endpoint: str, data: Optional[Dict]) -> None:
        """Task 154: Helper to execute an offline queued retry request and log success/fail telemetry."""
        res = self.request(method, endpoint, data, silent=True)
        with self._req_diag_lock:
            if res is not None and 200 <= res.status_code <= 299:
                self._offline_retry_success_count += 1
            else:
                self._offline_retry_fail_count += 1

    def get_offline_retry_telemetry(self) -> Dict[str, Any]:
        """Task 154: Returns automated offline request retry queue telemetry & execution success diagnostics."""
        with self._req_diag_lock:
            queued = self._offline_retry_queued_count
            executed = self._offline_retry_executed_count
            succeeded = self._offline_retry_success_count
            failed = self._offline_retry_fail_count
            dropped = self._offline_retry_dropped_count
            curr_len = len(self._offline_queue)
            success_rate_pct = round((succeeded / max(1, executed)) * 100.0, 2) if executed > 0 else 0.0

            return {
                "current_queue_len": curr_len,
                "max_queue_len": self._offline_queue_max,
                "queued_count": queued,
                "executed_count": executed,
                "success_count": succeeded,
                "fail_count": failed,
                "dropped_count": dropped,
                "execution_success_rate_pct": success_rate_pct,
            }

    def get_request_diagnostics(self) -> Dict[str, Any]:
        """Returns rate-limit throttle & retry status diagnostics for LCU HTTP requests."""
        with self._req_diag_lock:
            dist = {str(k): v for k, v in sorted(self._http_status_codes.items())}
            total_reqs = self._total_requests_count
            err_count = self._http_4xx_count + self._http_5xx_count + self._http_error_count
            err_rate = round((err_count / max(1, total_reqs)) * 100.0, 2)
            executed = self._offline_retry_executed_count
            succeeded = self._offline_retry_success_count
            success_rate_pct = round((succeeded / max(1, executed)) * 100.0, 2) if executed > 0 else 0.0

            diag = {
                "total_requests": total_reqs,
                "status_code_distribution": dist,
                "http_2xx_count": self._http_2xx_count,
                "http_3xx_count": self._http_3xx_count,
                "http_4xx_count": self._http_4xx_count,
                "http_5xx_count": self._http_5xx_count,
                "http_error_rate_pct": err_rate,
                "rate_limit_throttles": self._rate_limit_throttle_count,
                "total_throttle_sleep_s": round(self._total_throttle_sleep_s, 3),
                "offline_retry_queued": self._offline_retry_queued_count,
                "offline_retry_executed": self._offline_retry_executed_count,
                "offline_retry_success_count": self._offline_retry_success_count,
                "offline_retry_fail_count": self._offline_retry_fail_count,
                "offline_retry_dropped_count": self._offline_retry_dropped_count,
                "offline_retry_success_rate_pct": success_rate_pct,
                "http_429_count": self._http_429_count,
                "http_retry_count": self._http_retry_count,
                "http_error_count": self._http_error_count,
                "offline_queue_current_len": len(self._offline_queue),
                "adaptive_timeout_s": self.get_adaptive_http_timeout(),
            }
        hist = self.get_http_latency_histogram()
        diag["avg_latency_ms"] = hist["avg_latency_ms"]
        diag["p95_latency_ms"] = hist["p95_latency_ms"]
        diag["http_latency_variance_ms2"] = hist.get("http_latency_variance_ms2", 0.0)
        diag["http_latency_stddev_ms"] = hist.get("http_latency_stddev_ms", 0.0)
        diag["http_latency_skewness"] = hist.get("http_latency_skewness", 0.0)
        diag["http_latency_kurtosis"] = hist.get("http_latency_kurtosis", 0.0)
        diag.update(self.get_http_retry_jitter_entropy_telemetry())
        return diag

    # ─────────── WEBSOCKET PUBLISH / SUBSCRIBE ───────────

    def start_websocket(self):
        """Starts the persistent websocket thread if not running."""
        if self._ws_thread and self._ws_thread.is_alive():
            return
        
        self._ws_should_run = True
        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._ws_thread.start()

    def stop_websocket(self):
        """Stops the websocket thread."""
        self._ws_should_run = False
        if self._ws_connection:
            try:
                self._ws_connection.close()
            except Exception as e:
                Logger.debug("LCU_WS", f"WS close error (safe to ignore): {e}")
        if self._ws_executor:
            try:
                self._ws_executor.shutdown(wait=False)
            except Exception:
                pass
            self._ws_executor = None
        # Item #181: Join thread with timeout for clean shutdown
        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=3)

    def subscribe(self, event_name: str, callback):
        """Subscribes an event callback to the LCU WAMP WebSocket."""
        with self._lock:
            if event_name not in self._subscriptions:
                self._subscriptions[event_name] = []
                self._server_subscribe(event_name)
            if callback not in self._subscriptions[event_name]:
                self._subscriptions[event_name].append(callback)

    def _server_subscribe(self, event_name: str):
        if self._ws_connection:
            try:
                msg = [5, event_name]
                self._ws_connection.send(json.dumps(msg))
            except Exception as e:
                Logger.error("LCU_WS", f"Subscribe error: {e}")

    def _ws_loop(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        while self._ws_should_run:
            if not self.is_connected or not self.port or not self.auth_token:
                time.sleep(2)
                continue
            
            auth_str = f"riot:{self.auth_token}"
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            headers = {"Authorization": f"Basic {b64_auth}"}

            uri = f"wss://127.0.0.1:{self.port}"
            try:
                with ws_connect(uri, ssl=ctx, additional_headers=headers) as ws:
                    self._ws_connection = ws
                    self._ws_reconnect_backoff = 1.0  # Reset backoff on successful connection
                    self._ws_last_msg_timestamp = time.time()
                    with self._ws_telemetry_lock:
                        self._network_throttle_active = False
                    Logger.debug("LCU_WS", "WebSocket connected.")
                    
                    # Re-subscribe to all existing subscriptions
                    with self._lock:
                        for ev in self._subscriptions:
                            try:
                                msg = [5, ev]
                                ws.send(json.dumps(msg))
                            except Exception as e:
                                Logger.debug("LCU_WS", f"WS subscribe send failed: {e}")

                    while self._ws_should_run:
                        # Item #180 & Task 130: Timeout and dynamic heartbeat stale ping reset
                        try:
                            message = ws.recv(timeout=15)
                            self._ws_last_msg_timestamp = time.time()
                        except TimeoutError:
                            stale_timeout = self._effective_ws_stale_timeout()
                            stale_age = time.time() - self._ws_last_msg_timestamp
                            if stale_age >= stale_timeout:
                                # In-game: LCU is often quiet for long stretches — log at debug to cut noise
                                log_fn = Logger.debug if self._in_game_mode else Logger.warning
                                log_fn(
                                    "LCU_WS",
                                    f"Stale WebSocket connection ping timeout "
                                    f"({stale_age:.1f}s >= {stale_timeout:.1f}s without messages"
                                    f"{', in-game' if self._in_game_mode else ''}). Resetting connection.",
                                )
                                self._ws_stale_reset_count += 1
                                self._record_connection_drop(f"Stale WS ping timeout ({stale_age:.1f}s)")
                                try:
                                    ws.close()
                                except Exception:
                                    pass
                                break
                            continue
                        if not message:
                            continue
                            
                        self._record_ws_payload_metrics(message)
                        t_loop_start = time.perf_counter()
                        t_recv = time.perf_counter()
                        # WAMP v1 is JSON array
                        try:
                            # [8, "OnJsonApiEvent...", payload]
                            t_deser_start = time.perf_counter()
                            data = json.loads(message)
                            deser_latency_ms = (time.perf_counter() - t_deser_start) * 1000.0
                            self._record_ws_deser_telemetry(deser_latency_ms)
                            if isinstance(data, list) and len(data) >= 3 and data[0] == 8:
                                event_name = data[1]
                                payload = data[2]
                                
                                # 3.4 WAMP auto-normalization
                                try:
                                    if isinstance(payload, dict) and 'data' in payload and 'eventType' in payload:
                                        payload = payload['data']  # Normalize nested WAMP payload to flat data
                                except Exception as e:
                                    Logger.debug("LCU_WS", f"WAMP payload normalization failed: {e}")

                                # Emit to central EventBus (Phase 2 Rule)
                                from core.events import EventBus
                                EventBus.emit(event_name, payload)

                                # Find callbacks
                                callbacks = []
                                with self._lock:
                                    if event_name in self._subscriptions:
                                        callbacks = self._subscriptions[event_name].copy()
                                    if "OnJsonApiEvent" in self._subscriptions:
                                        callbacks.extend(self._subscriptions["OnJsonApiEvent"])
                                
                                t_dispatch_start = time.perf_counter()
                                for cb in callbacks:
                                    try:
                                        # Run callback in bounded pool so we don't stall the websocket
                                        if self._ws_executor is None:
                                            self._ws_executor = ThreadPoolExecutor(max_workers=4)
                                        self._ws_executor.submit(cb, event_name, payload)
                                    except Exception as e:
                                        Logger.error("LCU_WS", f"Callback error in {event_name}: {e}")

                                dispatch_latency_ms = (time.perf_counter() - t_dispatch_start) * 1000.0
                                self._record_ws_dispatch_telemetry(event_name, len(callbacks), dispatch_latency_ms)

                                # Record event latency telemetry
                                latency_ms = (time.perf_counter() - t_recv) * 1000.0
                                self._record_ws_telemetry(event_name, latency_ms)

                        except json.JSONDecodeError:
                            pass
                        except Exception as e:
                            Logger.error("LCU_WS", f"Message parse error: {e}")

                        # Task 133: Record event loop processing latency
                        loop_dur_ms = (time.perf_counter() - t_loop_start) * 1000.0
                        with self._ws_telemetry_lock:
                            self._event_loop_latency_ms = round(loop_dur_ms, 3)

            except ConnectionClosed as e:
                self._record_connection_drop(f"WebSocket ConnectionClosed: {e}")
                Logger.debug("LCU_WS", f"WebSocket closed normally or by server: {e}")
            except Exception as e:
                self._record_connection_drop(f"WebSocket connection failure: {e}")
                Logger.debug("LCU_WS", f"WebSocket connection failed: {e}")
            
            self._ws_connection = None
            # Task 127: Exponential backoff with random jitter for WS reconnection
            jitter = random.uniform(0.8, 1.2)
            sleep_duration = min(self._ws_reconnect_backoff * jitter, self._ws_max_backoff)
            Logger.debug("LCU_WS", f"WebSocket reconnecting in {sleep_duration:.2f}s (backoff={self._ws_reconnect_backoff:.1f}s)...")
            time.sleep(sleep_duration)
            self._ws_reconnect_backoff = min(self._ws_reconnect_backoff * 2.0, self._ws_max_backoff)

    def _record_connection_drop(self, reason: str):
        """Records connection drop diagnostics and evaluates network adapter state flap throttling."""
        now = time.time()
        with self._ws_telemetry_lock:
            self._connection_drop_count += 1
            self._last_drop_reason = reason
            self._drop_history.append((now, reason))
            if len(self._drop_history) > 20:
                self._drop_history.pop(0)

            # Task 136: Track drops within a 15-second window for adapter flap detection
            self._network_drop_timestamps.append(now)
            cutoff = now - 15.0
            while self._network_drop_timestamps and self._network_drop_timestamps[0] < cutoff:
                self._network_drop_timestamps.pop(0)

            if len(self._network_drop_timestamps) >= 3:
                self._network_throttle_active = True
                self._ws_reconnect_backoff = max(self._ws_reconnect_backoff, self._network_throttle_backoff_floor)
                Logger.warning(
                    "LCU_NETWORK_THROTTLE",
                    f"Rapid connection drops detected ({len(self._network_drop_timestamps)} drops in 15s). Enabling network adapter reconnect rate throttling (backoff floor={self._network_throttle_backoff_floor}s)."
                )

            Logger.info("LCU_DIAGNOSTICS", f"Connection drop recorded: {reason} (Total drops: {self._connection_drop_count})")

    def notify_network_state_change(self, state_info: str = "adapter_changed") -> None:
        """Notifies LCUClient of an OS or adapter-level network transition to dynamically adjust reconnect rate throttling."""
        with self._ws_telemetry_lock:
            self._network_adapter_changes += 1
        self._record_connection_drop(f"Network adapter state change: {state_info}")

    def _record_ws_payload_metrics(self, raw_message: Any) -> None:
        """Task 145: Records payload compression analysis and memory footprint metrics for incoming WS messages."""
        if not raw_message:
            return
        msg_bytes = raw_message.encode("utf-8") if isinstance(raw_message, str) else bytes(raw_message)
        payload_bytes = len(msg_bytes)

        with self._ws_telemetry_lock:
            self._ws_total_payload_bytes += payload_bytes
            self._ws_last_payload_bytes = payload_bytes
            if payload_bytes > self._ws_max_payload_bytes:
                self._ws_max_payload_bytes = payload_bytes

            self._ws_payload_samples.append(payload_bytes)
            if len(self._ws_payload_samples) > 200:
                self._ws_payload_samples.pop(0)

            # Compression analysis using zlib compression estimation
            try:
                comp_len = len(zlib.compress(msg_bytes, level=1))
            except Exception:
                comp_len = payload_bytes
            self._ws_compressed_bytes_est += comp_len
            self._ws_last_compression_ratio = round(payload_bytes / max(comp_len, 1), 2)

            # Task 166: Compressed payload size ratio anomaly detection
            ratio = self._ws_last_compression_ratio
            if ratio < self._ws_min_expected_compression_ratio or ratio > self._ws_max_expected_compression_ratio:
                self._ws_compression_anomaly_count += 1
                reason = "Ratio below min expected threshold" if ratio < self._ws_min_expected_compression_ratio else "Ratio above max expected threshold"
                anomaly_entry = {
                    "timestamp": time.time(),
                    "payload_bytes": payload_bytes,
                    "compressed_bytes": comp_len,
                    "compression_ratio": ratio,
                    "anomaly_reason": reason,
                }
                self._ws_compression_anomaly_history.append(anomaly_entry)
                if len(self._ws_compression_anomaly_history) > self._ws_compression_anomaly_history_max:
                    self._ws_compression_anomaly_history.pop(0)

            # Memory footprint of payload samples container
            self._ws_payload_memory_kb = round(sys.getsizeof(self._ws_payload_samples) / 1024.0, 3)

    def get_ws_compression_anomaly_telemetry(self) -> Dict[str, Any]:
        """Task 166: Returns automated websocket compressed payload size ratio anomaly telemetry."""
        with self._ws_telemetry_lock:
            anomalies = self._ws_compression_anomaly_count
            sample_cnt = len(self._ws_payload_samples)
            history = [dict(entry) for entry in self._ws_compression_anomaly_history]
            last_anomaly = dict(history[-1]) if history else None
            min_exp = self._ws_min_expected_compression_ratio
            max_exp = self._ws_max_expected_compression_ratio

        anomaly_rate = round(anomalies / max(sample_cnt, 1), 4) if sample_cnt > 0 else 0.0
        return {
            "ws_compression_anomaly_count": anomalies,
            "ws_compression_anomaly_rate": anomaly_rate,
            "ws_min_expected_compression_ratio": min_exp,
            "ws_max_expected_compression_ratio": max_exp,
            "last_compression_anomaly": last_anomaly,
            "recent_compression_anomalies": history,
        }

    def get_ws_payload_telemetry(self) -> Dict[str, Any]:
        """Task 145 & 166: Returns automated payload compression ratio, anomaly detection, and memory footprint analysis metrics."""
        with self._ws_telemetry_lock:
            samples = self._ws_payload_samples.copy()
            total_bytes = self._ws_total_payload_bytes
            last_bytes = self._ws_last_payload_bytes
            max_bytes = self._ws_max_payload_bytes
            comp_bytes = self._ws_compressed_bytes_est
            last_ratio = self._ws_last_compression_ratio
            mem_kb = self._ws_payload_memory_kb

        avg_bytes = round(sum(samples) / len(samples), 2) if samples else 0.0
        overall_ratio = round(total_bytes / max(comp_bytes, 1), 2) if comp_bytes > 0 else 1.0
        anomaly_meta = self.get_ws_compression_anomaly_telemetry()

        res = {
            "total_payload_bytes": total_bytes,
            "last_payload_bytes": last_bytes,
            "max_payload_bytes": max_bytes,
            "avg_payload_bytes": avg_bytes,
            "last_compression_ratio": last_ratio,
            "overall_compression_ratio": overall_ratio,
            "payload_sample_count": len(samples),
            "payload_memory_kb": mem_kb,
            "payload_memory_mb": round(mem_kb / 1024.0, 4),
        }
        res.update(anomaly_meta)
        return res


    def _record_ws_deser_telemetry(self, deser_latency_ms: float) -> None:
        """Task 148: Records WebSocket message payload deserialization latency samples and histogram metrics."""
        with self._ws_telemetry_lock:
            self._ws_deser_count += 1
            self._ws_last_deser_latency_ms = round(deser_latency_ms, 4)
            self._ws_deser_latency_samples.append(deser_latency_ms)
            if len(self._ws_deser_latency_samples) > 200:
                self._ws_deser_latency_samples.pop(0)

            if deser_latency_ms < self._ws_min_deser_latency_ms:
                self._ws_min_deser_latency_ms = deser_latency_ms
            if deser_latency_ms > self._ws_max_deser_latency_ms:
                self._ws_max_deser_latency_ms = deser_latency_ms

            if deser_latency_ms < 0.1:
                self._ws_deser_latency_buckets["<0.1ms"] += 1
            elif deser_latency_ms < 0.5:
                self._ws_deser_latency_buckets["0.1-0.5ms"] += 1
            elif deser_latency_ms < 1.0:
                self._ws_deser_latency_buckets["0.5-1.0ms"] += 1
            elif deser_latency_ms < 5.0:
                self._ws_deser_latency_buckets["1.0-5.0ms"] += 1
            else:
                self._ws_deser_latency_buckets[">5.0ms"] += 1

    def get_ws_deser_telemetry(self) -> Dict[str, Any]:
        """Task 148: Returns automated WS payload deserialization latency profiling metrics."""
        with self._ws_telemetry_lock:
            samples = self._ws_deser_latency_samples.copy()
            buckets = self._ws_deser_latency_buckets.copy()
            last_ms = self._ws_last_deser_latency_ms
            min_ms = round(self._ws_min_deser_latency_ms, 4) if self._ws_min_deser_latency_ms != float("inf") else 0.0
            max_ms = round(self._ws_max_deser_latency_ms, 4)
            count = self._ws_deser_count

        if samples:
            sorted_s = sorted(samples)
            p50 = round(sorted_s[int(len(sorted_s) * 0.50)], 4)
            p95 = round(sorted_s[min(int(len(sorted_s) * 0.95), len(sorted_s) - 1)], 4)
            p99 = round(sorted_s[min(int(len(sorted_s) * 0.99), len(sorted_s) - 1)], 4)
            avg = round(sum(samples) / len(samples), 4)
        else:
            p50 = p95 = p99 = avg = 0.0

        return {
            "deser_count": count,
            "last_deser_latency_ms": last_ms,
            "avg_deser_latency_ms": avg,
            "p50_deser_latency_ms": p50,
            "p95_deser_latency_ms": p95,
            "p99_deser_latency_ms": p99,
            "min_deser_latency_ms": min_ms,
            "max_deser_latency_ms": max_ms,
            "deser_histogram_buckets": buckets,
            "deser_sample_count": len(samples),
        }

    def _acquire_deser_buffer(self) -> Dict[str, Any]:
        """Task 160: Acquires a recycled dictionary buffer from the deserialization pool or creates a new dictionary."""
        with self._ws_telemetry_lock:
            if self._ws_deser_pool:
                self._ws_deser_recycle_hits += 1
                buf = self._ws_deser_pool.pop()
                buf.clear()
                return buf
            else:
                self._ws_deser_recycle_misses += 1
                return {}

    def _recycle_deser_buffer(self, obj: Any) -> None:
        """Task 160: Recycles a dictionary object back into the deserialization pool if capacity permits."""
        if isinstance(obj, dict):
            with self._ws_telemetry_lock:
                if len(self._ws_deser_pool) < self._ws_deser_pool_max_size:
                    obj.clear()
                    self._ws_deser_pool.append(obj)
                    self._ws_deser_bytes_recycled += sys.getsizeof(obj)

    def clear_ws_deser_pool(self) -> None:
        """Task 160: Clears the recycled JSON deserialization memory pool."""
        with self._ws_telemetry_lock:
            self._ws_deser_pool.clear()

    def get_ws_deser_pool_telemetry(self) -> Dict[str, Any]:
        """Task 160: Returns automated websocket JSON deserialization memory pool recycling metrics."""
        with self._ws_telemetry_lock:
            pool_size = len(self._ws_deser_pool)
            hits = self._ws_deser_recycle_hits
            misses = self._ws_deser_recycle_misses
            tot = hits + misses
            hit_ratio = round(hits / tot, 4) if tot > 0 else 0.0
            bytes_rec = self._ws_deser_bytes_recycled
            pool_mem_kb = round(sys.getsizeof(self._ws_deser_pool) / 1024.0, 3)

            return {
                "deser_pool_size": pool_size,
                "deser_pool_max_size": self._ws_deser_pool_max_size,
                "deser_recycle_hits": hits,
                "deser_recycle_misses": misses,
                "deser_recycle_hit_ratio": hit_ratio,
                "deser_bytes_recycled": bytes_rec,
                "deser_pool_memory_kb": pool_mem_kb,
            }

    def _acquire_decomp_buffer(self, size: int = 1024) -> bytearray:
        """Task 163: Acquires a recycled bytearray buffer from the decompression pool or creates a new bytearray."""
        with self._ws_telemetry_lock:
            if self._ws_decomp_pool:
                self._ws_decomp_recycle_hits += 1
                buf = self._ws_decomp_pool.pop()
                if len(buf) < size:
                    buf.extend(b"\x00" * (size - len(buf)))
                return buf
            else:
                self._ws_decomp_recycle_misses += 1
                return bytearray(size)

    def _recycle_decomp_buffer(self, buf: Any) -> None:
        """Task 163: Recycles a bytearray buffer back into the decompression pool if capacity permits."""
        if isinstance(buf, bytearray):
            with self._ws_telemetry_lock:
                if len(self._ws_decomp_pool) < self._ws_decomp_pool_max_size:
                    self._ws_decomp_pool.append(buf)
                    self._ws_decomp_bytes_recycled += sys.getsizeof(buf)

    def clear_ws_decomp_pool(self) -> None:
        """Task 163: Clears the recycled websocket decompression memory pool."""
        with self._ws_telemetry_lock:
            self._ws_decomp_pool.clear()

    def get_ws_decomp_pool_telemetry(self) -> Dict[str, Any]:
        """Task 163: Returns automated websocket decompression memory pool recycling metrics."""
        with self._ws_telemetry_lock:
            pool_size = len(self._ws_decomp_pool)
            hits = self._ws_decomp_recycle_hits
            misses = self._ws_decomp_recycle_misses
            tot = hits + misses
            hit_ratio = round(hits / tot, 4) if tot > 0 else 0.0
            bytes_rec = self._ws_decomp_bytes_recycled
            pool_mem_kb = round(sys.getsizeof(self._ws_decomp_pool) / 1024.0, 3)

            return {
                "decomp_pool_size": pool_size,
                "decomp_pool_max_size": self._ws_decomp_pool_max_size,
                "decomp_recycle_hits": hits,
                "decomp_recycle_misses": misses,
                "decomp_recycle_hit_ratio": hit_ratio,
                "decomp_bytes_recycled": bytes_rec,
                "decomp_pool_memory_kb": pool_mem_kb,
            }

    def _record_ws_dispatch_telemetry(self, event_name: str, callbacks_count: int, dispatch_latency_ms: float) -> None:
        """Task 157: Records websocket subscription filter performance metrics & callback dispatch telemetry."""
        with self._ws_telemetry_lock:
            self._ws_dispatch_count += 1
            self._ws_total_dispatched_callbacks += callbacks_count
            self._ws_dispatch_total_latency_ms += dispatch_latency_ms
            if dispatch_latency_ms > self._ws_max_dispatch_latency_ms:
                self._ws_max_dispatch_latency_ms = dispatch_latency_ms

    def get_ws_dispatch_telemetry(self) -> Dict[str, Any]:
        """Task 157: Returns automated websocket subscription filter performance metrics & dispatch latency telemetry."""
        with self._ws_telemetry_lock:
            count = self._ws_dispatch_count
            total_cbs = self._ws_total_dispatched_callbacks
            tot_lat = self._ws_dispatch_total_latency_ms
            avg_lat = round(tot_lat / max(1, count), 3) if count > 0 else 0.0
            avg_cbs = round(total_cbs / max(1, count), 2) if count > 0 else 0.0
            max_lat = round(self._ws_max_dispatch_latency_ms, 3)

        with self._lock:
            active_filters = len(self._subscriptions)
            total_listeners = sum(len(cbs) for cbs in self._subscriptions.values())

        return {
            "active_subscription_filters": active_filters,
            "total_registered_listeners": total_listeners,
            "dispatch_event_count": count,
            "dispatched_callbacks_count": total_cbs,
            "avg_dispatched_callbacks_per_event": avg_cbs,
            "avg_dispatch_latency_ms": avg_lat,
            "max_dispatch_latency_ms": max_lat,
        }

    def _record_ws_telemetry(self, event_name: str, latency_ms: float):
        """Records websocket message processing latency and throughput telemetry with burst anomaly detection."""
        now = time.time()
        is_anomaly = False
        with self._ws_telemetry_lock:
            self._ws_event_count += 1
            self._ws_last_latency_ms = latency_ms
            self._ws_latency_samples.append(latency_ms)
            if len(self._ws_latency_samples) > 200:
                self._ws_latency_samples.pop(0)
            self._ws_event_timestamps.append(now)
            cutoff = now - 10.0
            while self._ws_event_timestamps and self._ws_event_timestamps[0] < cutoff:
                self._ws_event_timestamps.pop(0)

            # Latency anomaly evaluation
            is_anomaly = latency_ms > self._ws_anomaly_threshold_ms
            recent_count = len(self._ws_event_timestamps)
            # Active burst alert when high event throughput coincides with latency anomalies
            self._ws_burst_alert_active = (recent_count >= 25) or (is_anomaly and recent_count >= 10)

            if is_anomaly:
                self._ws_anomaly_count += 1
                Logger.warning(
                    "LCU_WS_ANOMALY",
                    f"Latency anomaly detected on {event_name}: {latency_ms:.2f}ms (threshold: {self._ws_anomaly_threshold_ms}ms)"
                )

        if latency_ms > 50.0 and not is_anomaly:
            Logger.warning("LCU_WS_PERF", f"High event latency on {event_name}: {latency_ms:.2f}ms")

    def get_ws_telemetry(self) -> Dict[str, Any]:
        """Returns telemetry performance metrics and WAMP throughput for LCU websocket event processing."""
        now = time.time()
        payload_meta = self.get_ws_payload_telemetry()
        deser_meta = self.get_ws_deser_telemetry()
        deser_pool_meta = self.get_ws_deser_pool_telemetry()
        decomp_pool_meta = self.get_ws_decomp_pool_telemetry()
        dispatch_meta = self.get_ws_dispatch_telemetry()
        with self._ws_telemetry_lock:
            cutoff = now - 10.0
            while self._ws_event_timestamps and self._ws_event_timestamps[0] < cutoff:
                self._ws_event_timestamps.pop(0)

            cutoff_drop = now - 15.0
            while self._network_drop_timestamps and self._network_drop_timestamps[0] < cutoff_drop:
                self._network_drop_timestamps.pop(0)
            recent_drops_15s = len(self._network_drop_timestamps)
            
            recent_count = len(self._ws_event_timestamps)
            rolling_throughput_eps = round(recent_count / 10.0, 2)
            
            elapsed = max(now - self._ws_start_time, 0.001)
            overall_throughput_eps = round(self._ws_event_count / elapsed, 2)
            last_msg_age_s = round(now - self._ws_last_msg_timestamp, 2) if self._ws_connection else 0.0

            uptime_s = round(now - self._last_connected_timestamp, 2) if self.is_connected and self._last_connected_timestamp > 0 else 0.0

            res = {
                "total_events": self._ws_event_count,
                "last_latency_ms": round(self._ws_last_latency_ms, 3) if self._ws_latency_samples else 0.0,
                "avg_latency_ms": round(sum(self._ws_latency_samples) / len(self._ws_latency_samples), 3) if self._ws_latency_samples else 0.0,
                "max_latency_ms": round(max(self._ws_latency_samples), 3) if self._ws_latency_samples else 0.0,
                "min_latency_ms": round(min(self._ws_latency_samples), 3) if self._ws_latency_samples else 0.0,
                "sample_count": len(self._ws_latency_samples),
                "throughput_eps": rolling_throughput_eps,
                "overall_throughput_eps": overall_throughput_eps,
                "throughput_window_s": 10.0,
                "anomaly_count": self._ws_anomaly_count,
                "anomaly_threshold_ms": self._ws_anomaly_threshold_ms,
                "burst_alert_active": self._ws_burst_alert_active,
                "reconnect_backoff_s": round(self._ws_reconnect_backoff, 2),
                "last_msg_age_s": last_msg_age_s,
                "stale_reset_count": self._ws_stale_reset_count,
                "stale_timeout_s": self._effective_ws_stale_timeout(),
                "stale_timeout_base_s": self._ws_stale_timeout_s,
                "stale_timeout_ingame_s": self._ws_stale_timeout_ingame_s,
                "in_game_mode": self._in_game_mode,
                "connection_drop_count": self._connection_drop_count,
                "last_drop_reason": self._last_drop_reason,
                "event_loop_latency_ms": self._event_loop_latency_ms,
                "connection_uptime_s": uptime_s,
                "network_throttle_active": self._network_throttle_active,
                "network_adapter_changes": self._network_adapter_changes,
                "recent_drops_15s": recent_drops_15s,
            }
            res.update(payload_meta)
            res.update(deser_meta)
            res.update(deser_pool_meta)
            res.update(decomp_pool_meta)
            res.update(dispatch_meta)
            return res
