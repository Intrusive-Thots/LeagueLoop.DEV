import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.leagueloop_diagnostics import (
    get_leagueloop_paths,
    read_tail_bounded,
    inspect_error_log,
    inspect_crash_log,
    inspect_session_log,
    inspect_debug_log,
    inspect_screenshots,
    classify_screenshot_event,
    run_diagnostics,
)


class TestLeagueLoopDiagnostics(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.logs_dir = self.base / "logs"
        self.screenshots_dir = self.base / "debug_screenshots"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        self.paths = {
            "base": self.base,
            "logs": self.logs_dir,
            "screenshots": self.screenshots_dir,
            "error_log": self.logs_dir / "error.log",
            "crash_log": self.logs_dir / "crash.log",
            "debug_log": self.logs_dir / "debug.log",
            "session_log": self.logs_dir / "session.jsonl",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_leagueloop_paths_structure(self):
        p = get_leagueloop_paths()
        self.assertIn("error_log", p)
        self.assertIn("crash_log", p)
        self.assertIn("screenshots", p)
        self.assertIn("fallback_screenshots", p)

    def test_inspect_error_log_empty_and_missing(self):
        missing_res = inspect_error_log(self.paths["error_log"])
        self.assertFalse(missing_res["exists"])

        self.paths["error_log"].write_text("", encoding="utf-8")
        empty_res = inspect_error_log(self.paths["error_log"])
        self.assertTrue(empty_res["exists"])
        self.assertEqual(len(empty_res["recent_errors"]), 0)
        self.assertEqual(len(empty_res["recent_warnings"]), 0)

    def test_inspect_error_log_parses_levels(self):
        log_content = (
            "2026-10-14 10:00:00 INFO [Main] App starting\n"
            "2026-10-14 10:01:00 WARNING [Net] Network latency high\n"
            "2026-10-14 10:02:00 WARNING [WS] [LCU_WS_ANOMALY] packet dropped\n"
            "2026-10-14 10:03:00 ERROR [API] [LCU_NETWORK_THROTTLE] Rate limit hit\n"
            "2026-10-14 10:04:00 CRITICAL [Core] Unhandled exception occurred\n"
        )
        self.paths["error_log"].write_text(log_content, encoding="utf-8")
        res = inspect_error_log(self.paths["error_log"])

        self.assertEqual(res["total_lines_inspected"], 5)
        self.assertEqual(res["ws_anomalies_count"], 1)
        self.assertEqual(res["network_throttles_count"], 1)
        self.assertEqual(len(res["recent_errors"]), 2)  # ERROR + CRITICAL
        self.assertEqual(len(res["recent_warnings"]), 1)  # WARNING without anomaly tag

    def test_inspect_crash_log_distinguishes_sessions_from_crashes(self):
        # 5 normal sessions without crashes
        normal_sessions = (
            "--- session 101 2026-10-14T01:00:00-04:00 ---\n\n"
            "--- session 102 2026-10-14T02:00:00-04:00 ---\n\n"
            "--- session 103 2026-10-14T03:00:00-04:00 ---\n\n"
        )
        self.paths["crash_log"].write_text(normal_sessions, encoding="utf-8")
        res = inspect_crash_log(self.paths["crash_log"])

        self.assertEqual(res["total_sessions_tracked"], 3)
        self.assertEqual(res["total_actual_crashes"], 0)
        self.assertEqual(len(res["recent_crashes"]), 0)
        self.assertEqual(res["total_crash_sessions"], 0)

    def test_inspect_crash_log_detects_actual_crashes(self):
        crash_log_content = (
            "--- session 101 2026-08-24T00:56:16-04:00 ---\n"
            "Windows fatal exception: access violation\n"
            "Thread 0x00004e30 (most recent call first):\n"
            "  File \"ssl.py\", line 1105 in read\n\n"
            "--- session 102 2026-10-14T01:00:00-04:00 ---\n\n"
            "--- session 103 2026-10-14T02:00:00-04:00 ---\n\n"
        )
        self.paths["crash_log"].write_text(crash_log_content, encoding="utf-8")
        res = inspect_crash_log(self.paths["crash_log"], max_sessions=2)

        self.assertEqual(res["total_sessions_tracked"], 3)
        self.assertEqual(res["total_actual_crashes"], 1)
        # Session 101 is not in the last 2 sessions (102, 103), so recent_crashes is empty
        self.assertEqual(len(res["recent_crashes"]), 0)
        self.assertIn("latest_historical_crash", res)
        self.assertEqual(res["latest_historical_crash"]["session"], "--- session 101 2026-08-24T00:56:16-04:00 ---")

    def test_classify_screenshot_event(self):
        cat, event = classify_screenshot_event("20261014_104444_setting_hotkey_find_match.png")
        self.assertEqual(cat, "hotkey_setting")
        self.assertEqual(event, "setting_hotkey_find_match")

        cat, event = classify_screenshot_event("20261014_104339_find_match_clicked.png")
        self.assertEqual(cat, "button_click")
        self.assertEqual(event, "find_match_clicked")

        cat, event = classify_screenshot_event("20261014_104328_tab_switch.png")
        self.assertEqual(cat, "tab_transition")
        self.assertEqual(event, "tab_switch")

        cat, event = classify_screenshot_event("20261014_082013_game_phase_change.png")
        self.assertEqual(cat, "game_phase_change")

        cat, event = classify_screenshot_event("20261014_081942_queue_search_started.png")
        self.assertEqual(cat, "queue_action")

        cat, event = classify_screenshot_event("champion_hover_ahri.png")
        self.assertEqual(cat, "champion_action")

    def test_inspect_screenshots(self):
        (self.screenshots_dir / "capture_1.png").write_bytes(b"image_data_1")
        (self.screenshots_dir / "capture_2.png").write_bytes(b"image_data_2")
        captures = inspect_screenshots(self.screenshots_dir, max_count=5)
        self.assertEqual(len(captures), 2)
        self.assertEqual(captures[0]["source"], "primary")

    def test_inspect_screenshots_with_fallback(self):
        fallback_dir = self.base / "fallback_captures"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        (fallback_dir / "20261014_100000_tab_switch.png").write_bytes(b"fallback_img")

        # Primary screenshots dir is empty; should use fallback
        captures = inspect_screenshots(self.screenshots_dir, max_count=5, fallback_path=fallback_dir)
        self.assertEqual(len(captures), 1)
        self.assertEqual(captures[0]["source"], "fallback")
        self.assertEqual(captures[0]["category"], "tab_transition")

        # When primary has images, it prefers primary
        (self.screenshots_dir / "20261014_110000_find_match_clicked.png").write_bytes(b"primary_img")
        captures_prim = inspect_screenshots(self.screenshots_dir, max_count=5, fallback_path=fallback_dir)
        self.assertEqual(len(captures_prim), 1)
        self.assertEqual(captures_prim[0]["source"], "primary")
        self.assertEqual(captures_prim[0]["category"], "button_click")

    def test_inspect_session_log(self):
        # Missing file
        missing_res = inspect_session_log(self.paths["session_log"])
        self.assertFalse(missing_res["exists"])

        # Valid session log entries
        entries = [
            '{"ts": "2026-10-14T10:00:00", "level": "INFO", "tag": "START", "session": "s1", "msg": "Booted"}',
            '{"ts": "2026-10-14T10:01:00", "level": "WARNING", "tag": "LCU_NETWORK_THROTTLE", "session": "s1", "msg": "Backoff"}',
            '{"ts": "2026-10-14T10:02:00", "level": "INFO", "tag": "LOOP", "session": "s2", "msg": "Tick"}',
        ]
        self.paths["session_log"].write_text("\n".join(entries), encoding="utf-8")
        res = inspect_session_log(self.paths["session_log"], max_entries=10)

        self.assertTrue(res["exists"])
        self.assertEqual(res["total_entries"], 3)
        self.assertEqual(len(res["recent_entries"]), 3)
        self.assertEqual(res["level_counts"].get("INFO"), 2)
        self.assertEqual(res["level_counts"].get("WARNING"), 1)
        self.assertIn("s1", res["active_sessions"])
        self.assertIn("s2", res["active_sessions"])
        self.assertEqual(len(res["recent_anomalies_or_throttles"]), 1)

    def test_run_diagnostics_healthy_and_unhealthy(self):
        # Clean state -> healthy
        self.paths["error_log"].write_text("INFO Clean", encoding="utf-8")
        self.paths["crash_log"].write_text("--- session 1 ---\n", encoding="utf-8")
        diag = run_diagnostics(self.paths)
        self.assertTrue(diag["healthy"])

        # Error in log -> unhealthy
        self.paths["error_log"].write_text("ERROR Crash in service", encoding="utf-8")
        diag_err = run_diagnostics(self.paths)
        self.assertFalse(diag_err["healthy"])

    def test_run_diagnostics_custom_limits(self):
        log_lines = "\n".join([f"2026-10-14 10:0{i}:00 INFO line {i}" for i in range(10)])
        self.paths["error_log"].write_text(log_lines, encoding="utf-8")
        diag = run_diagnostics(self.paths, max_lines=4)
        self.assertEqual(len(diag["error_analysis"]["recent_errors"]), 0)

    def test_read_tail_bounded(self):
        sample_file = self.base / "tail_test.txt"
        count, tail = read_tail_bounded(sample_file, max_lines=5)
        self.assertEqual(count, 0)
        self.assertEqual(tail, [])

        sample_file.write_text("\n".join([f"line_{i}" for i in range(20)]), encoding="utf-8")
        count, tail = read_tail_bounded(sample_file, max_lines=5)
        self.assertEqual(count, 20)
        self.assertEqual(len(tail), 5)
        self.assertEqual(tail[-1].strip(), "line_19")

    def test_inspect_error_log_with_rotated_log(self):
        # Current log has 2 lines, rotated has error
        self.paths["error_log"].write_text("INFO Clean recent 1\nINFO Clean recent 2\n", encoding="utf-8")
        rotated_log = self.logs_dir / "error.log.1"
        rotated_log.write_text("ERROR Failure prior to rollover\n", encoding="utf-8")

        res_without = inspect_error_log(self.paths["error_log"], max_lines=2, include_rotated=False)
        self.assertFalse(res_without["rotated_log_inspected"])
        self.assertEqual(len(res_without["recent_errors"]), 0)

        # Asking for 5 lines triggers rotated fallback because total_lines (2) < max_lines (5)
        res_with = inspect_error_log(self.paths["error_log"], max_lines=5)
        self.assertTrue(res_with["rotated_log_inspected"])
        self.assertEqual(len(res_with["recent_errors"]), 1)
        self.assertIn("Failure prior to rollover", res_with["recent_errors"][0])

    def test_inspect_debug_log(self):
        # Missing file
        missing_res = inspect_debug_log(self.paths["debug_log"])
        self.assertFalse(missing_res["exists"])

        debug_content = (
            "2026-10-14 12:00:00 INFO [Main] Starting up\n"
            "2026-10-14 12:00:01 DEBUG [Net] Initializing connection\n"
            "2026-10-14 12:00:02 WARNING [WS] [LCU_WS_ANOMALY] Latency 150ms\n"
            "2026-10-14 12:00:03 INFO [Diag] [LCU_DIAGNOSTICS] Connection drop recorded: Flap\n"
            "2026-10-14 12:00:04 WARNING [Throttle] [LCU_NETWORK_THROTTLE] Rate backoff enabled\n"
        )
        self.paths["debug_log"].write_text(debug_content, encoding="utf-8")
        res = inspect_debug_log(self.paths["debug_log"], max_lines=10)

        self.assertTrue(res["exists"])
        self.assertEqual(res["total_lines_inspected"], 5)
        self.assertEqual(len(res["recent_entries"]), 5)
        self.assertEqual(res["level_counts"].get("INFO"), 2)
        self.assertEqual(res["level_counts"].get("DEBUG"), 1)
        self.assertEqual(res["level_counts"].get("WARNING"), 2)
        self.assertEqual(res["diagnostic_tags_count"], 3)
        self.assertEqual(len(res["recent_diagnostics"]), 3)

    def test_main_cli_verbose(self):
        from tools.leagueloop_diagnostics import main
        self.paths["error_log"].write_text("INFO Clean", encoding="utf-8")
        self.paths["crash_log"].write_text("--- session 1 ---\n", encoding="utf-8")
        self.paths["debug_log"].write_text("2026-10-14 INFO [LCU_DIAGNOSTICS] Test event\n", encoding="utf-8")

        with patch("sys.stdout"):
            with patch("tools.leagueloop_diagnostics.get_leagueloop_paths", return_value=self.paths):
                with patch("sys.argv", ["leagueloop_diagnostics.py", "-v", "--summary"]):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()

