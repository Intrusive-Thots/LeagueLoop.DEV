"""
Unit tests for ImageCacheService disk cache scanning and pruning.
"""
import os
import time
from services.image_cache import ImageCacheService


def test_get_disk_cache_stats(tmp_path):
    service = ImageCacheService(cache_dir=str(tmp_path))

    # Create dummy files
    f1 = tmp_path / "processed_test.png"
    f1.write_bytes(b"12345")
    f2 = tmp_path / "raw_icon.jpg"
    f2.write_bytes(b"1234567890")

    stats = service.get_disk_cache_stats()
    assert stats["total_files"] == 2
    assert stats["total_bytes"] == 15
    assert stats["processed_count"] == 1
    assert stats["raw_image_count"] == 1
    assert stats["cache_dir"] == str(tmp_path)


def test_get_disk_cache_stats_ttl_caching(tmp_path):
    service = ImageCacheService(cache_dir=str(tmp_path))
    f1 = tmp_path / "processed_test.png"
    f1.write_bytes(b"12345")

    stats1 = service.get_disk_cache_stats()
    assert stats1["total_files"] == 1

    # Add another file without forcing scan
    f2 = tmp_path / "processed_test2.png"
    f2.write_bytes(b"12345")

    stats2 = service.get_disk_cache_stats()
    assert stats2["total_files"] == 1  # From cache

    telemetry = service.get_disk_cache_scan_telemetry()
    assert telemetry["disk_scan_cache_hits"] == 1

    # Force scan
    stats3 = service.get_disk_cache_stats(force_scan=True)
    assert stats3["total_files"] == 2


def test_clean_disk_cache(tmp_path):
    service = ImageCacheService(cache_dir=str(tmp_path))

    for i in range(10):
        f = tmp_path / f"img_{i}.png"
        f.write_bytes(b"x" * 100)
        os.utime(f, (time.time() - (10 - i) * 10, time.time() - (10 - i) * 10))

    result = service.clean_disk_cache(max_files=5, max_bytes=10000, max_age_days=30)
    assert result["removed_files"] == 5
    assert result["freed_bytes"] == 500

    remaining = [p for p in tmp_path.iterdir() if p.is_file()]
    assert len(remaining) == 5
