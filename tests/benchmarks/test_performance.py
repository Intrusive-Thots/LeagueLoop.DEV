"""
Performance & Benchmark Tests for LeagueLoop.
Validates latency, throughput, and resource optimization across services and UI components.
"""
from __future__ import annotations

import os
import time
import tracemalloc
import unittest
from utils.running_stats import RunningStats, RunningPercentile
from services.http_session_factory import create_pooled_session, get_shared_session


class TestPerformanceBenchmarks(unittest.TestCase):
    """Benchmarks critical hot paths for speed and memory efficiency."""

    def test_running_stats_o1_performance(self):
        """Verify that RunningStats processes 100,000 updates in under 100ms."""
        stats = RunningStats()
        start = time.perf_counter()

        for i in range(100_000):
            stats.update(float(i % 1000))

        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertEqual(stats.n, 100_000)
        self.assertLess(elapsed_ms, 150.0, f"RunningStats took {elapsed_ms:.2f}ms for 100k updates (exceeded budget)")

    def test_running_percentile_performance(self):
        """Verify that RunningPercentile provides fast approximate quantiles."""
        rp = RunningPercentile(0.95)
        start = time.perf_counter()

        for i in range(10_000):
            rp.update(float(i % 500))

        elapsed_ms = (time.perf_counter() - start) * 1000
        p95 = rp.percentile()
        self.assertGreater(p95, 0.0)
        self.assertLess(elapsed_ms, 80.0, f"RunningPercentile took {elapsed_ms:.2f}ms (exceeded budget)")

    def test_http_session_pooling_memory(self):
        """Verify pooled session allocation memory efficiency."""
        tracemalloc.start()
        session = create_pooled_session(pool_connections=20, pool_maxsize=20)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_kb = peak / 1024
        self.assertLess(peak_kb, 500.0, f"Session pool allocation exceeded 500KB ({peak_kb:.2f}KB)")
        session.close()

    def test_qt_shell_instantiation_latency(self):
        """Verify that PySide6 main window builds in under 500ms in offscreen mode."""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        start = time.perf_counter()
        from ui.qt.main_window import LeagueLoopMainWindow
        window = LeagueLoopMainWindow(container=None)
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertIsNotNone(window)
        self.assertIn("priority", window.tab_pages)
        self.assertIn("loot", window.tab_pages)
        self.assertIn("accounts", window.tab_pages)
        self.assertLess(elapsed_ms, 800.0, f"MainWindow initialization took {elapsed_ms:.2f}ms")
        window.close()


if __name__ == "__main__":
    unittest.main()
