---
name: ws_payload_and_disk_prune_optimization
description: Automated WebSocket payload compression analysis, memory footprint reporting, and disk cache auto-prune time-threshold evaluation under high download throughput.
---

# WebSocket Payload & Disk Cache Prune Optimization Protocol

## Overview
Provides structured patterns for tracking raw WebSocket payload memory footprints, calculating zlib compression ratios, and throttling disk cache auto-prune scans under high asset download throughput.

## Patterns

### 1. WebSocket Payload Compression & Memory Telemetry (`LCUClient`)
- **Metric Tracking**: Calculate `payload_bytes`, total payload bytes, peak message size, rolling averages, and sample buffer memory (`sys.getsizeof`).
- **Zlib Ratio Estimation**: Estimate payload compression ratios on incoming WS frames via `zlib.compress(msg, level=1)`.
- **Telemetry Export**: Expose `get_ws_payload_telemetry()` metrics:
  - `total_payload_bytes`, `last_payload_bytes`, `max_payload_bytes`, `avg_payload_bytes`
  - `last_compression_ratio`, `overall_compression_ratio`
  - `payload_sample_count`, `payload_memory_kb`, `payload_memory_mb`

### 2. Disk Cache Auto-Prune Time-Threshold Evaluation (`AssetManager`)
- **Time Throttling**: Throttle soft file/byte limit auto-pruning checks (`_prune_check_interval_s = 2.0s`) to avoid frequent disk `os.scandir` scans during high download throughput.
- **Bypass Flag**: Support `force=True` parameter to bypass time-threshold check during manual or explicit cache cleanups.
- **Metrics Export**: Expose `get_disk_cache_prune_metrics()` detailing check count, skipped count, prune execution count, and total auto-freed megabytes.
