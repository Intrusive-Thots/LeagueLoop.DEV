---
name: disk_cache_cleanup_strategy
description: LRU disk cache pruning strategy for DDragon image assets during high asset churn.
---

# Disk Cache Cleanup Strategy Skill

## Overview
Automates file size and file count benchmarking and cleanup for DDragon asset cache directory under high asset churn.

## Key Logic
- Scan `CACHE_DIR` using `os.scandir` to prevent blocking memory allocation.
- Ignore core metadata files (`version.txt`, `champion.json`, `item.json`, `meraki_champions.json`).
- Sort cache items by modification time `mtime` (oldest first).
- Prune items exceeding max age (`max_age_days=14`), max file count (`max_files=500`), or max directory bytes (`max_bytes=50MB`).
- Benchmark execution latency and log total pruned files and freed megabytes.
