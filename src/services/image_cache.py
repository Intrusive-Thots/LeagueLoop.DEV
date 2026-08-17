"""
Image Cache Service for LeagueLoop.
Provides disk cache metrics, scanning with TTL, high-churn auto-pruning,
and memory optimization for champion assets.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional

from utils.logger import Logger
from utils.path_utils import get_data_dir

CACHE_DIR = os.path.join(get_data_dir(), "cache")


class ImageCacheService:
    """Manages disk asset caching, TTL scanning, and LRU eviction policies."""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or CACHE_DIR
        self._lock = threading.RLock()
        self._cached_disk_stats: Optional[Dict[str, Any]] = None
        self._disk_stats_scan_timestamp: float = 0.0
        self._disk_stats_cache_ttl_s: float = 3.0
        self._disk_scan_count: int = 0
        self._disk_scan_cache_hits: int = 0
        self._disk_scan_total_latency_ms: float = 0.0

        os.makedirs(self.cache_dir, exist_ok=True)

    def get_disk_cache_stats(self, force_scan: bool = False) -> Dict[str, Any]:
        """Benchmark and optimize disk cache subfolder scanning performance with TTL caching."""
        with self._lock:
            now = time.time()
            if not force_scan and self._cached_disk_stats is not None:
                if (now - self._disk_stats_scan_timestamp) < self._disk_stats_cache_ttl_s:
                    self._disk_scan_cache_hits += 1
                    return self._cached_disk_stats

        t_start = time.perf_counter()
        total_files = 0
        total_bytes = 0
        processed_count = 0
        raw_image_count = 0

        if os.path.exists(self.cache_dir):
            for entry in os.scandir(self.cache_dir):
                if entry.is_file():
                    total_files += 1
                    try:
                        total_bytes += entry.stat().st_size
                    except OSError:
                        pass
                    if entry.name.startswith("processed_"):
                        processed_count += 1
                    elif entry.name.endswith((".png", ".jpg", ".jpeg", ".webp")):
                        raw_image_count += 1

        scan_dur_ms = (time.perf_counter() - t_start) * 1000.0

        stats = {
            "total_files": total_files,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "processed_count": processed_count,
            "raw_image_count": raw_image_count,
            "cache_dir": self.cache_dir,
        }

        with self._lock:
            self._cached_disk_stats = stats
            self._disk_stats_scan_timestamp = time.time()
            self._disk_scan_count += 1
            self._disk_scan_total_latency_ms += scan_dur_ms

        return stats

    def get_disk_cache_scan_telemetry(self) -> Dict[str, Any]:
        """Returns benchmark and optimization metrics for disk cache scanning performance."""
        with self._lock:
            scans = self._disk_scan_count
            hits = self._disk_scan_cache_hits
            tot_lat = self._disk_scan_total_latency_ms
            avg_lat = round(tot_lat / max(1, scans), 3) if scans > 0 else 0.0
            return {
                "disk_scan_count": scans,
                "disk_scan_cache_hits": hits,
                "avg_scan_latency_ms": avg_lat,
                "scan_ttl_seconds": self._disk_stats_cache_ttl_s,
            }

    def clean_disk_cache(
        self,
        max_files: int = 500,
        max_bytes: int = 50 * 1024 * 1024,
        max_age_days: int = 14,
    ) -> Dict[str, Any]:
        """
        Benchmarks and executes disk cache cleanup strategy during high asset churn.
        Removes oldest cache files if file count, total bytes, or max age thresholds are exceeded.
        """
        t_start = time.perf_counter()
        removed_count = 0
        freed_bytes = 0

        if not os.path.exists(self.cache_dir):
            return {
                "removed_files": 0,
                "freed_bytes": 0,
                "freed_mb": 0.0,
                "duration_ms": round((time.perf_counter() - t_start) * 1000, 2),
            }

        now = time.time()
        max_age_sec = max_age_days * 86400

        files_info = []
        for entry in os.scandir(self.cache_dir):
            if not entry.is_file():
                continue
            # Do not delete critical system metadata
            if entry.name in ("version.txt", "champion.json", "item.json", "meraki_champions.json"):
                continue
            try:
                st = entry.stat()
                files_info.append({
                    "path": entry.path,
                    "name": entry.name,
                    "mtime": st.st_mtime,
                    "size": st.st_size,
                })
            except OSError:
                continue

        # Sort files by modification time (oldest first)
        files_info.sort(key=lambda x: x["mtime"])
        files_to_remove = set()

        # 1. Expired files
        for f in files_info:
            if (now - f["mtime"]) > max_age_sec:
                files_to_remove.add(f["path"])

        # 2. Prune if count exceeds limit
        remaining = [f for f in files_info if f["path"] not in files_to_remove]
        if len(remaining) > max_files:
            excess = len(remaining) - max_files
            for f in remaining[:excess]:
                files_to_remove.add(f["path"])

        # 3. Prune if size exceeds limit
        remaining = [f for f in files_info if f["path"] not in files_to_remove]
        current_size = sum(f["size"] for f in remaining)
        if current_size > max_bytes:
            for f in remaining:
                if current_size <= max_bytes:
                    break
                files_to_remove.add(f["path"])
                current_size -= f["size"]

        # Execute removal
        for path in files_to_remove:
            try:
                sz = os.path.getsize(path)
                os.remove(path)
                removed_count += 1
                freed_bytes += sz
            except OSError as e:
                Logger.warning("ImageCacheService", f"Failed to prune cache file {path}: {e}")

        duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
        with self._lock:
            self._cached_disk_stats = None

        return {
            "removed_files": removed_count,
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "duration_ms": duration_ms,
        }
