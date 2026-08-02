"""
Unit tests and benchmark for DDragon image disk cache cleanup strategy during high asset churn.
"""
import os
import time
import pytest
from services.asset_manager import AssetManager, CACHE_DIR


def test_get_disk_cache_stats():
    am = AssetManager()
    stats = am.get_disk_cache_stats()
    assert "total_files" in stats
    assert "total_bytes" in stats
    assert "total_mb" in stats
    assert "processed_count" in stats
    assert "raw_image_count" in stats
    assert stats["cache_dir"] == CACHE_DIR


def test_clean_disk_cache_no_op(tmp_path, monkeypatch):
    monkeypatch.setattr("services.asset_manager.CACHE_DIR", str(tmp_path))
    am = AssetManager()
    
    result = am.clean_disk_cache(max_files=10, max_bytes=10000)
    assert result["removed_files"] == 0
    assert result["freed_bytes"] == 0


def test_clean_disk_cache_max_files(tmp_path, monkeypatch):
    monkeypatch.setattr("services.asset_manager.CACHE_DIR", str(tmp_path))
    am = AssetManager()

    # Create 20 mock cache files
    for i in range(20):
        f_path = tmp_path / f"processed_test_{i}.png"
        f_path.write_bytes(b"x" * 100)
        # Stagger modification times
        os.utime(f_path, (time.time() - (20 - i) * 10, time.time() - (20 - i) * 10))

    # Clean with max_files=10
    result = am.clean_disk_cache(max_files=10, max_bytes=100000, max_age_days=30)
    assert result["removed_files"] == 10
    assert result["freed_bytes"] == 1000

    remaining = [p for p in tmp_path.iterdir() if p.is_file()]
    assert len(remaining) == 10


def test_clean_disk_cache_max_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr("services.asset_manager.CACHE_DIR", str(tmp_path))
    am = AssetManager()

    # Create 10 mock files of 1KB each
    for i in range(10):
        f_path = tmp_path / f"cached_img_{i}.png"
        f_path.write_bytes(b"a" * 1024)
        os.utime(f_path, (time.time() - (10 - i) * 5, time.time() - (10 - i) * 5))

    # Clean with max_bytes=4KB (4096 bytes)
    result = am.clean_disk_cache(max_files=100, max_bytes=4096, max_age_days=30)
    assert result["removed_files"] >= 5
    remaining_size = sum(p.stat().st_size for p in tmp_path.iterdir() if p.is_file())
    assert remaining_size <= 4096


def test_benchmark_high_asset_churn(tmp_path, monkeypatch):
    monkeypatch.setattr("services.asset_manager.CACHE_DIR", str(tmp_path))
    am = AssetManager()

    # Create 300 mock cache files simulating high churn
    for i in range(300):
        f_path = tmp_path / f"churn_asset_{i}.png"
        f_path.write_bytes(b"data" * 256)  # 1KB file
        os.utime(f_path, (time.time() - (300 - i) * 2, time.time() - (300 - i) * 2))

    t_start = time.perf_counter()
    result = am.clean_disk_cache(max_files=50, max_bytes=100 * 1024, max_age_days=30)
    duration_ms = (time.perf_counter() - t_start) * 1000

    assert result["removed_files"] == 250
    assert duration_ms < 500.0  # Cleanup of 250 files should complete under 500ms on Windows IO


def test_splash_art_memory_eviction():
    am = AssetManager()
    am.max_splash_icons = 5
    
    # Insert mock splash items into splash_icons
    for i in range(10):
        key = f"splash_100{i}_1280_1.0"
        am.splash_icons[key] = f"mock_image_{i}"

    stats_before = am.get_splash_memory_stats()
    assert stats_before["splash_count"] == 10
    assert stats_before["max_splash_count"] == 5

    evicted = am.evict_splash_art_memory()
    assert evicted == 5
    stats_after = am.get_splash_memory_stats()
    assert stats_after["splash_count"] == 5


def test_check_auto_prune_disk_cache_trigger(tmp_path, monkeypatch):
    monkeypatch.setattr("services.asset_manager.CACHE_DIR", str(tmp_path))
    am = AssetManager()

    # Create 20 mock cache files
    for i in range(20):
        f_path = tmp_path / f"auto_prune_{i}.png"
        f_path.write_bytes(b"data" * 10)
        os.utime(f_path, (time.time() - (20 - i) * 5, time.time() - (20 - i) * 5))

    # Calling check_auto_prune with file_limit=15 should trigger clean_disk_cache
    res = am.check_auto_prune_disk_cache(file_limit=15, bytes_limit=100000, force=True)
    assert res is not None
    assert res["removed_files"] >= 1


def test_auto_prune_disk_cache_time_threshold_throttling(tmp_path, monkeypatch):
    monkeypatch.setattr("services.asset_manager.CACHE_DIR", str(tmp_path))
    am = AssetManager()
    am._prune_check_interval_s = 2.0

    # First check triggers full evaluation
    res1 = am.check_auto_prune_disk_cache(file_limit=100, bytes_limit=100000)
    assert res1 is None
    
    # Rapid subsequent call within 2 seconds should be throttled and skipped
    res2 = am.check_auto_prune_disk_cache(file_limit=100, bytes_limit=100000)
    assert res2 is None

    metrics = am.get_disk_cache_prune_metrics()
    assert metrics["prune_check_count"] == 2
    assert metrics["prune_check_skipped_count"] == 1
    assert metrics["prune_check_interval_s"] == 2.0

    # Force check overrides time threshold
    res3 = am.check_auto_prune_disk_cache(file_limit=100, bytes_limit=100000, force=True)
    assert res3 is None
    metrics2 = am.get_disk_cache_prune_metrics()
    assert metrics2["prune_check_count"] == 3
    assert metrics2["prune_check_skipped_count"] == 1


