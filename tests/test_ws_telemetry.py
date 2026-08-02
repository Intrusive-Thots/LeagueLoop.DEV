"""
Unit tests for LCU websocket performance latency telemetry.
"""
import pytest
import time
from services.api_handler import LCUClient


def test_lcu_client_ws_telemetry_initial_state():
    client = LCUClient()
    telemetry = client.get_ws_telemetry()
    assert telemetry["total_events"] == 0
    assert telemetry["last_latency_ms"] == 0.0
    assert telemetry["avg_latency_ms"] == 0.0
    assert telemetry["sample_count"] == 0
    assert telemetry["throughput_eps"] == 0.0
    assert telemetry["overall_throughput_eps"] >= 0.0
    assert telemetry["throughput_window_s"] == 10.0


def test_lcu_client_ws_telemetry_recording():
    client = LCUClient()
    client._record_ws_telemetry("OnJsonApiEvent_lol_gameflow_v1_gameflow_phase", 2.5)
    client._record_ws_telemetry("OnJsonApiEvent_lol_champ_select_v1_session", 4.1)

    telemetry = client.get_ws_telemetry()
    assert telemetry["total_events"] == 2
    assert telemetry["last_latency_ms"] == 4.1
    assert telemetry["avg_latency_ms"] == pytest.approx(3.3, 0.1)
    assert telemetry["max_latency_ms"] == 4.1
    assert telemetry["min_latency_ms"] == 2.5
    assert telemetry["sample_count"] == 2
    assert telemetry["throughput_eps"] == 0.2
    assert telemetry["overall_throughput_eps"] > 0.0


def test_lcu_client_ws_telemetry_high_latency_warning(caplog):
    client = LCUClient()
    client._record_ws_telemetry("OnJsonApiEvent_slow_event", 75.0)

    telemetry = client.get_ws_telemetry()
    assert telemetry["total_events"] == 1
    assert telemetry["last_latency_ms"] == 75.0


def test_lcu_client_ws_telemetry_rolling_window():
    client = LCUClient()
    for i in range(250):
        client._record_ws_telemetry("event", float(i))

    telemetry = client.get_ws_telemetry()
    assert telemetry["total_events"] == 250
    assert telemetry["sample_count"] == 200
    assert telemetry["min_latency_ms"] == 50.0
    assert telemetry["max_latency_ms"] == 249.0
    assert telemetry["throughput_eps"] == 25.0


def test_lcu_client_ws_telemetry_anomaly_alerting():
    client = LCUClient()
    # Normal event below 100ms threshold
    client._record_ws_telemetry("OnJsonApiEvent_normal", 15.0)
    t1 = client.get_ws_telemetry()
    assert t1["anomaly_count"] == 0
    assert t1["burst_alert_active"] is False

    # Event exceeding anomaly threshold (100ms)
    client._record_ws_telemetry("OnJsonApiEvent_spike", 150.0)
    t2 = client.get_ws_telemetry()
    assert t2["anomaly_count"] == 1

    # Simulate burst of 25 events
    for _ in range(24):
        client._record_ws_telemetry("OnJsonApiEvent_burst", 5.0)
    
    t3 = client.get_ws_telemetry()
    assert t3["total_events"] == 26
    assert t3["burst_alert_active"] is True


def test_lcu_client_ws_reconnect_backoff_and_jitter():
    client = LCUClient()
    t_initial = client.get_ws_telemetry()
    assert t_initial["reconnect_backoff_s"] == 1.0

    # Simulate connection failure backoff increment
    client._ws_reconnect_backoff = min(client._ws_reconnect_backoff * 2.0, client._ws_max_backoff)
    t1 = client.get_ws_telemetry()
    assert t1["reconnect_backoff_s"] == 2.0

    client._ws_reconnect_backoff = min(client._ws_reconnect_backoff * 2.0, client._ws_max_backoff)
    t2 = client.get_ws_telemetry()
    assert t2["reconnect_backoff_s"] == 4.0

    # Reset backoff on reconnect
    client._ws_reconnect_backoff = 1.0
    t_reset = client.get_ws_telemetry()
    assert t_reset["reconnect_backoff_s"] == 1.0


def test_lcu_client_ws_heartbeat_and_stale_ping_timeout():
    client = LCUClient()
    t_initial = client.get_ws_telemetry()
    assert t_initial["stale_reset_count"] == 0
    assert t_initial["stale_timeout_s"] == 45.0
    assert "last_msg_age_s" in t_initial

    # Simulate stale connection age exceeding threshold
    client._ws_last_msg_timestamp = time.time() - 50.0
    client._ws_stale_reset_count += 1
    t1 = client.get_ws_telemetry()
    assert t1["stale_reset_count"] == 1

    # Simulate timestamp refresh on active message receive
    client._ws_last_msg_timestamp = time.time()
    t2 = client.get_ws_telemetry()
    assert t2["stale_reset_count"] == 1


def test_lcu_client_connection_drop_and_event_loop_telemetry():
    client = LCUClient()
    t0 = client.get_ws_telemetry()
    assert t0["connection_drop_count"] == 0
    assert t0["last_drop_reason"] == ""
    assert t0["event_loop_latency_ms"] == 0.0
    assert t0["connection_uptime_s"] == 0.0

    # Simulate recording connection drop
    client._record_connection_drop("Test simulated connection drop")
    t1 = client.get_ws_telemetry()
    assert t1["connection_drop_count"] == 1
    assert t1["last_drop_reason"] == "Test simulated connection drop"

    # Simulate event loop processing latency
    with client._ws_telemetry_lock:
        client._event_loop_latency_ms = 1.25
        client._last_connected_timestamp = time.time() - 120.0
        client.is_connected = True

    t2 = client.get_ws_telemetry()
    assert t2["event_loop_latency_ms"] == 1.25
    assert t2["connection_uptime_s"] >= 119.0


def test_lcu_client_network_adapter_reconnect_throttling():
    client = LCUClient()
    t0 = client.get_ws_telemetry()
    assert t0["network_throttle_active"] is False
    assert t0["network_adapter_changes"] == 0
    assert t0["recent_drops_15s"] == 0

    # Notify network state change
    client.notify_network_state_change("WiFi to Ethernet flap")
    t1 = client.get_ws_telemetry()
    assert t1["network_adapter_changes"] == 1
    assert t1["recent_drops_15s"] == 1
    assert t1["network_throttle_active"] is False

    # Simulate rapid consecutive drops triggering rate throttling
    client._record_connection_drop("Rapid drop 2")
    client._record_connection_drop("Rapid drop 3")
    
    t2 = client.get_ws_telemetry()
    assert t2["recent_drops_15s"] == 3
    assert t2["network_throttle_active"] is True
    assert client._ws_reconnect_backoff >= 5.0


def test_lcu_client_ws_payload_compression_and_memory_telemetry():
    client = LCUClient()
    payload_initial = client.get_ws_payload_telemetry()
    assert payload_initial["total_payload_bytes"] == 0
    assert payload_initial["last_payload_bytes"] == 0
    assert payload_initial["max_payload_bytes"] == 0
    assert payload_initial["avg_payload_bytes"] == 0.0
    assert payload_initial["last_compression_ratio"] == 1.0
    assert payload_initial["overall_compression_ratio"] == 1.0
    assert payload_initial["payload_sample_count"] == 0

    # Simulate recording WS payload message
    mock_msg = '{"eventType": "Update", "uri": "/lol-gameflow/v1/gameflow-phase", "data": "ChampSelect"}' * 5
    client._record_ws_payload_metrics(mock_msg)

    payload_after = client.get_ws_payload_telemetry()
    assert payload_after["total_payload_bytes"] > 0
    assert payload_after["last_payload_bytes"] == len(mock_msg)
    assert payload_after["max_payload_bytes"] == len(mock_msg)
    assert payload_after["avg_payload_bytes"] == float(len(mock_msg))
    assert payload_after["last_compression_ratio"] >= 1.0
    assert payload_after["overall_compression_ratio"] >= 1.0
    assert payload_after["payload_sample_count"] == 1
    assert payload_after["payload_memory_kb"] >= 0.0

    # Verify inclusion in general get_ws_telemetry()
    t = client.get_ws_telemetry()
    assert "total_payload_bytes" in t
    assert "overall_compression_ratio" in t
    assert "payload_memory_mb" in t


def test_lcu_client_ws_deser_telemetry():
    client = LCUClient()
    initial = client.get_ws_deser_telemetry()
    assert initial["deser_count"] == 0
    assert initial["last_deser_latency_ms"] == 0.0
    assert initial["avg_deser_latency_ms"] == 0.0
    assert initial["min_deser_latency_ms"] == 0.0
    assert initial["max_deser_latency_ms"] == 0.0
    assert initial["deser_sample_count"] == 0
    assert "<0.1ms" in initial["deser_histogram_buckets"]

    # Record deserialization latency samples
    client._record_ws_deser_telemetry(0.05)
    client._record_ws_deser_telemetry(0.35)
    client._record_ws_deser_telemetry(1.20)

    after = client.get_ws_deser_telemetry()
    assert after["deser_count"] == 3
    assert after["last_deser_latency_ms"] == 1.20
    assert after["min_deser_latency_ms"] == 0.05
    assert after["max_deser_latency_ms"] == 1.20
    assert after["deser_sample_count"] == 3
    assert after["avg_deser_latency_ms"] > 0.0
    assert after["deser_histogram_buckets"]["<0.1ms"] == 1
    assert after["deser_histogram_buckets"]["0.1-0.5ms"] == 1
    assert after["deser_histogram_buckets"]["1.0-5.0ms"] == 1

    # Verify inclusion in general get_ws_telemetry()
    t = client.get_ws_telemetry()
    assert "deser_count" in t
    assert "last_deser_latency_ms" in t
    assert "deser_histogram_buckets" in t


def test_lcu_client_ws_dispatch_telemetry():
    client = LCUClient()
    initial = client.get_ws_dispatch_telemetry()
    assert initial["active_subscription_filters"] == 0
    assert initial["total_registered_listeners"] == 0
    assert initial["dispatch_event_count"] == 0
    assert initial["dispatched_callbacks_count"] == 0

    # Subscribe dummy callback
    cb = lambda e, p: None
    client.subscribe("OnJsonApiEvent_lol_gameflow_v1_gameflow_phase", cb)

    # Record dispatch telemetry
    client._record_ws_dispatch_telemetry("OnJsonApiEvent_lol_gameflow_v1_gameflow_phase", 1, 0.45)

    after = client.get_ws_dispatch_telemetry()
    assert after["active_subscription_filters"] == 1
    assert after["total_registered_listeners"] == 1
    assert after["dispatch_event_count"] == 1
    assert after["dispatched_callbacks_count"] == 1
    assert after["avg_dispatched_callbacks_per_event"] == 1.0
    assert after["avg_dispatch_latency_ms"] == 0.45
    assert after["max_dispatch_latency_ms"] == 0.45

    # Verify inclusion in general get_ws_telemetry()
    t = client.get_ws_telemetry()
    assert "active_subscription_filters" in t
    assert "dispatched_callbacks_count" in t
    assert "avg_dispatch_latency_ms" in t


def test_lcu_client_ws_deser_memory_pool_recycling():
    client = LCUClient()
    initial = client.get_ws_deser_pool_telemetry()
    assert initial["deser_pool_size"] == 0
    assert initial["deser_recycle_hits"] == 0
    assert initial["deser_recycle_misses"] == 0
    assert initial["deser_recycle_hit_ratio"] == 0.0

    # Acquire new buffer (miss)
    buf1 = client._acquire_deser_buffer()
    assert isinstance(buf1, dict)
    buf1["test_key"] = "test_val"

    # Recycle buffer back into pool
    client._recycle_deser_buffer(buf1)

    pool_after_recycle = client.get_ws_deser_pool_telemetry()
    assert pool_after_recycle["deser_pool_size"] == 1
    assert pool_after_recycle["deser_bytes_recycled"] > 0

    # Acquire again (hit from pool)
    buf2 = client._acquire_deser_buffer()
    assert "test_key" not in buf2  # Cleared on acquisition

    after_hit = client.get_ws_deser_pool_telemetry()
    assert after_hit["deser_pool_size"] == 0
    assert after_hit["deser_recycle_hits"] == 1
    assert after_hit["deser_recycle_misses"] == 1
    assert after_hit["deser_recycle_hit_ratio"] == 0.5

    # Clear pool
    client._recycle_deser_buffer(buf2)
    client.clear_ws_deser_pool()
    assert client.get_ws_deser_pool_telemetry()["deser_pool_size"] == 0

    # Verify inclusion in general get_ws_telemetry()
    t = client.get_ws_telemetry()
    assert "deser_pool_size" in t
    assert "deser_recycle_hits" in t
    assert "deser_recycle_hit_ratio" in t


def test_lcu_client_ws_decomp_memory_pool_recycling():
    client = LCUClient()
    initial = client.get_ws_decomp_pool_telemetry()
    assert initial["decomp_pool_size"] == 0
    assert initial["decomp_recycle_hits"] == 0
    assert initial["decomp_recycle_misses"] == 0
    assert initial["decomp_recycle_hit_ratio"] == 0.0

    # Acquire new buffer (miss)
    buf1 = client._acquire_decomp_buffer(1024)
    assert isinstance(buf1, bytearray)
    assert len(buf1) == 1024

    # Recycle buffer back into pool
    client._recycle_decomp_buffer(buf1)

    pool_after_recycle = client.get_ws_decomp_pool_telemetry()
    assert pool_after_recycle["decomp_pool_size"] == 1
    assert pool_after_recycle["decomp_bytes_recycled"] > 0

    # Acquire again (hit from pool)
    buf2 = client._acquire_decomp_buffer(2048)
    assert isinstance(buf2, bytearray)
    assert len(buf2) >= 2048

    after_hit = client.get_ws_decomp_pool_telemetry()
    assert after_hit["decomp_pool_size"] == 0
    assert after_hit["decomp_recycle_hits"] == 1
    assert after_hit["decomp_recycle_misses"] == 1
    assert after_hit["decomp_recycle_hit_ratio"] == 0.5

    # Clear pool
    client._recycle_decomp_buffer(buf2)
    client.clear_ws_decomp_pool()
    assert client.get_ws_decomp_pool_telemetry()["decomp_pool_size"] == 0

    # Verify inclusion in general get_ws_telemetry()
    t = client.get_ws_telemetry()
    assert "decomp_pool_size" in t
    assert "decomp_recycle_hits" in t
    assert "decomp_recycle_hit_ratio" in t


def test_lcu_client_ws_compressed_payload_ratio_anomaly_detection():
    client = LCUClient()
    initial_anomaly = client.get_ws_compression_anomaly_telemetry()
    assert initial_anomaly["ws_compression_anomaly_count"] == 0
    assert initial_anomaly["last_compression_anomaly"] is None
    assert initial_anomaly["ws_compression_anomaly_rate"] == 0.0

    # Simulate normal message
    client._record_ws_payload_metrics('{"event": "normal_event", "data": "abc"}')
    t_normal = client.get_ws_payload_telemetry()
    assert t_normal["ws_compression_anomaly_count"] == 0

    # Set threshold tight to trigger anomaly
    client._ws_min_expected_compression_ratio = 1.0
    client._ws_max_expected_compression_ratio = 1.05
    client._record_ws_payload_metrics('{"event": "test_anomaly", "data": "' + ("A" * 5000) + '"}')

    t_anomaly = client.get_ws_payload_telemetry()
    assert t_anomaly["ws_compression_anomaly_count"] >= 1
    assert t_anomaly["last_compression_anomaly"] is not None
    assert "anomaly_reason" in t_anomaly["last_compression_anomaly"]
    assert t_anomaly["ws_compression_anomaly_rate"] > 0.0

    # Verify inclusion in get_ws_telemetry()
    full_t = client.get_ws_telemetry()
    assert "ws_compression_anomaly_count" in full_t
    assert "last_compression_anomaly" in full_t


def test_lcu_client_http_latency_skewness_kurtosis_telemetry():
    client = LCUClient()
    initial = client.get_http_latency_skewness_kurtosis_telemetry()
    assert initial["http_latency_skewness"] == 0.0
    assert initial["http_latency_kurtosis"] == 0.0
    assert initial["http_latency_excess_kurtosis"] == 0.0
    assert initial["sample_count"] == 0

    for lat in [10.0, 10.0, 10.0, 10.0, 100.0]:
        client._record_http_latency(lat)

    meta = client.get_http_latency_skewness_kurtosis_telemetry()
    assert meta["sample_count"] == 5
    assert meta["http_latency_skewness"] > 0.0
    assert meta["http_latency_kurtosis"] > 0.0
    assert "http_latency_excess_kurtosis" in meta

    hist = client.get_http_latency_histogram()
    assert "http_latency_skewness" in hist
    assert "http_latency_kurtosis" in hist

    diag = client.get_request_diagnostics()
    assert "http_latency_skewness" in diag
    assert "http_latency_kurtosis" in diag










