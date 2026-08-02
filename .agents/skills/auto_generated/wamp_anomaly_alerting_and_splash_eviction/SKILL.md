---
name: wamp_anomaly_alerting_and_splash_eviction
description: Autonomous pattern for WAMP latency anomaly alerting and high-resolution splash art preview memory eviction.
---

# WAMP Anomaly Alerting & Splash Art Memory Eviction Strategy

## 1. Latency Anomaly Alerting & Burst Tracking
- In `src/services/api_handler.py`:
  - Maintains `_ws_anomaly_count`, `_ws_anomaly_threshold_ms`, and `_ws_burst_alert_active` state.
  - When `latency_ms > _ws_anomaly_threshold_ms` (default 100ms), triggers structured `Logger.warning("LCU_WS_ANOMALY", ...)` and increments anomaly metrics.
  - Flags burst activity (`_ws_burst_alert_active`) when event throughput spikes above 2.5 eps with latency anomalies.
  - Exposes `anomaly_count`, `anomaly_threshold_ms`, and `burst_alert_active` via `get_ws_telemetry()`.

## 2. High-Resolution Splash Art Memory Eviction
- In `src/services/asset_manager.py`:
  - Maintains dedicated `self.splash_icons` `OrderedDict` LRU cache separate from standard thumbnail icons.
  - Enforces `max_splash_icons = 15` limit to prevent memory bloat from large 1920x1080 preview assets.
  - Provides `evict_splash_art_memory(max_splash_count)` and `get_splash_memory_stats()`.
