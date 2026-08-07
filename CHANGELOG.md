# LeagueLoop.DEV Changelog

All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.08.149] - 2026-08-07

- **Duclos-Esteban-Ray (DER) & Zhang-Kanbur Polarization Telemetry**: Implemented `get_http_retry_jitter_der_zhang_polarization_telemetry()` in `LCUClient` (`src/services/api_handler.py`) to compute DER index and Zhang-Kanbur polarization inequality metrics on HTTP request retry exponential backoff jitter distributions.
- **Champion Rune Stat Shards Recommendations Memory Pooling**: Implemented `_acquire_rune_stat_shards_search_slice_tuple()`, `search_rune_stat_shards_recommendations()`, and `get_rune_stat_shards_search_slice_pool_telemetry()` in `AssetManager` (`src/services/asset_manager.py`), enabling slice tuple memory recycling for rune stat shards queries.
- **Expanded Test Suite & Pre-Flight Build Validation**: Added `test_http_retry_jitter_der_zhang_polarization_telemetry` in `tests/test_api_handler.py` and `test_rune_stat_shards_recommendations_memory_pooling` in `tests/test_asset_manager.py`, expanding test suite to 210 passing tests (`210 passed in 1.32s`) and passing `tools/build_validator.py` pre-flight verification.

## [1.07.153] - 2026-07-31

- **WebSocket Subscription Dispatch Telemetry**: Implemented `_record_ws_dispatch_telemetry()` and `get_ws_dispatch_telemetry()` in `LCUClient` (`src/services/api_handler.py`) to track active filters, registered listeners, dispatched callbacks count, and average/max dispatch latency.
- **Champion Search Index Lookup Performance**: Implemented indexed search normalization and benchmarking (`_champ_search_index`, `search_champions()`, `get_champ_search_telemetry()`) in `AssetManager` (`src/services/asset_manager.py`), enabling fast sub-millisecond filtering by name, key, role, and tag.
- **Adaptive HTTP Client Timeout Adjustment**: Implemented latency sliding-window histogram tracking (`_http_latency_samples`, `_http_latency_buckets`) and dynamic p95-based adaptive request timeout calculation (`LCUClient.get_adaptive_http_timeout()`, `get_http_latency_histogram()`) in `src/services/api_handler.py`, preventing HTTP thread starvation during LCU latency spikes.
- **Champion Skin Icon Memory Optimization**: Implemented dedicated LRU memory cache (`skin_icons`, `max_skin_icons = 80`) and memory eviction (`AssetManager.get_skin_icon()`, `evict_skin_icon_memory()`) in `src/services/asset_manager.py`, capping skin preview RAM usage.
- **Expanded Unit Test Suite**: Added `test_adaptive_http_timeout_and_latency_histogram` in `tests/test_api_handler.py` and `test_skin_icon_memory_optimization_and_eviction` in `tests/test_asset_manager.py`, expanding test suite to 158 passing tests (`158 passed in 0.82s`).
- **Dynamic WebSocket Heartbeat & Stale Ping Timeout Reset**: Implemented dynamic message timestamp tracking (`_ws_last_msg_timestamp`), staleness timeout thresholding (`_ws_stale_timeout_s = 45.0s`), and automatic connection reset (`_ws_stale_reset_count`) in `LCUClient` (`src/services/api_handler.py`), preventing silent socket drops on quiet LCU connections.
- **Champion Tags & Meraki Roles Memory Optimization**: Applied `sys.intern` string interning and immutable tuple conversions for `AssetManager.id_to_tags` and `champ_roles` (`src/services/asset_manager.py`), significantly reducing memory allocations for repeated tag and role strings.
- **Automated WS Reconnection Exponential Jitter Backoff**: Implemented exponential backoff with jitter (`_ws_reconnect_backoff` scaling to 30.0s) in `LCUClient` (`src/services/api_handler.py`), exported via `get_ws_telemetry()`.
- **Champ Select Disk Cache Auto-Pruning**: Integrated `check_auto_prune_disk_cache()` triggers in `AssetManager` (`src/services/asset_manager.py`) during champ select asset pre-fetches.
- **Expanded Unit Test Suite**: Added `test_lcu_client_ws_heartbeat_and_stale_ping_timeout` in `tests/test_ws_telemetry.py` and `test_interned_tags_and_roles` in `tests/test_asset_manager.py`, expanding test suite to 151 passing tests (`151 passed in 0.81s`).
- **LCU Sleep/Wake Reconnection Recovery**: Added system sleep/wake time-gap detection (>15s) and `LCUClient.reset_sleep_wake_backoff()` (`src/services/api_handler.py`) to eliminate exponential penalty delays upon system wake, emitting `lcu_sleep_wake_recovery` events on `EventBus`.
- **Adaptive Spectator Polling Rate Throttle**: Implemented `_spectate_start_time` tracking and dynamic spectator long-polling fallback (`TICK_SLEEP_SPECTATING` 15.0s scaling up to 30.0s) in `AutomationEngine` (`src/services/automation.py`), minimizing CPU and network load while spectating games.
- **Expanded Unit Test Suite**: Added test cases for sleep/wake backoff reset in `tests/test_lcu_reconnect.py` and spectator mode polling throttle in `tests/test_automation.py`, expanding the unit test suite to 143 passing tests.
- **LCU WAMP Event Throughput Export**: Extended `LCUClient.get_ws_telemetry()` (`src/services/api_handler.py`) with rolling and overall WAMP throughput metrics (`throughput_eps`, `overall_throughput_eps`, `throughput_window_s`).
- **Champ Select Roll Phase Asset Prefetching**: Optimized `AssetManager.preload_champion_icons()` and wired automatic icon pre-fetching into `AutomationEngine._handle_champ_select()` during active roll phases in ARAM and Champ Select.
- **LCU WAMP Event Latency Telemetry**: Implemented `get_ws_telemetry()` and high-latency warning system in `LCUClient` (`src/services/api_handler.py`) to monitor event dispatch performance.
- **DDragon Disk Cache Cleanup Strategy**: Added `clean_disk_cache()` and `get_disk_cache_stats()` to `AssetManager` (`src/services/asset_manager.py`) for LRU pruning during high asset churn, backed by high-churn benchmark tests.
- **Expanded Test Coverage**: Created `tests/test_ws_telemetry.py` and `tests/test_asset_cache_cleanup.py`, bringing the test suite to 139 unit & integration tests (`139 passed in 5.02s`).
- **Headless UI Testing Skill**: Added `.agents/skills/auto_generated/headless_ui_testing/SKILL.md` documenting the `sys.modules` mocking pattern for CustomTkinter and Tkinter widgets.
- **Repository Management Documents**: Created and synchronized `IMPLEMENTATION_PLAN.md`, `TASK_QUEUE.md`, `ROADMAP.md`, `CHANGELOG.md`, and `TODO.md` in the repository root.
- **Autonomous Memory Records**: Updated `memory/episodic.json`, `memory/failures.json`, `memory/procedural.json`, and `memory/optimizations.json` with the latest test suite and build verification metrics.

### Fixed
- **Headless CustomTkinter Test Instantiation**: Resolved `_tkinter.TclError: Can't find a usable init.tcl` in `tests/test_ui_kwargs.py` by implementing headless `sys.modules` CustomTkinter/Tkinter mocking in `TestUIKwargs`.

### Verified
- **100% Test Pass Rate**: Verified that all 137 unit and integration tests pass cleanly (`137 passed in 6.05s`).
- **Release Readiness**: Executed `tools/build_validator.py` pre-flight pipeline, confirming `BUILD READINESS: READY FOR COMPILATION`.
