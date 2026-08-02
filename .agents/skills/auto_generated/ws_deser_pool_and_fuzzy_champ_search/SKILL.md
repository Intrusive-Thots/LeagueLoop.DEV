# Skill: ws_deser_pool_and_fuzzy_champ_search

## Description
Autonomous improvement pattern for recycling WebSocket JSON deserialization memory pool buffers in `LCUClient` and benchmarking fuzzy matching champion search query latency in `AssetManager`.

## Logic Pattern
1. **WS Deserialization Memory Pool Recycling (`LCUClient`)**:
   - `_acquire_deser_buffer()`: Retrieves recycled dictionary buffer from `_ws_deser_pool` or creates a new dict, tracking hits and misses.
   - `_recycle_deser_buffer(obj)`: Clears and returns dictionary back to `_ws_deser_pool` if pool size < `_ws_deser_pool_max_size`.
   - `get_ws_deser_pool_telemetry()`: Exports metrics including pool size, recycle hits/misses, hit ratio, bytes recycled, and memory footprint.
2. **Fuzzy Champion Search & Benchmarking (`AssetManager`)**:
   - Pre-computes champion initials/acronyms and search features during index build (`_build_champ_search_index`).
   - `search_champions()`: Fast substring search first; falls back to fuzzy matching, scoring exact, prefix, initials, substring, and subsequence matches.
   - `_champ_search_fuzzy_cache`: LRU cache for fuzzy search results.
   - `get_fuzzy_search_telemetry()`: Exports fuzzy search count, hits, misses, hit ratio, cache size, and average latency.
