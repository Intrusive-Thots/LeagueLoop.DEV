---
name: ws_dispatch_telemetry_and_champ_search_index
description: WebSocket subscription dispatch latency telemetry and champion search index pre-normalization and performance benchmarking.
---

# WebSocket Subscription Dispatch Telemetry & Champion Search Index Skill

## Overview
Provides real-time performance telemetry for WebSocket subscriber event dispatching and optimizes champion search filtering via pre-normalized index lookups.

## Key Implementation Patterns
1. **WebSocket Dispatch Telemetry**:
   - Record `_ws_dispatch_count`, `_ws_total_dispatched_callbacks`, `_ws_dispatch_total_latency_ms`, and `_ws_max_dispatch_latency_ms` in `LCUClient`.
   - Export dispatch performance metrics via `get_ws_dispatch_telemetry()`.
2. **Champion Search Indexing & Benchmarking**:
   - Construct `_champ_search_index` in `AssetManager._build_champ_search_index()` with lowercased keys/names, interned tags, and roles.
   - Filter champions in sub-millisecond queries via `AssetManager.search_champions(query, role, tag, limit)`.
   - Benchmark query count and latency via `get_champ_search_telemetry()`.
