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
    inspect_saved_sessions,
    inspect_storage_usage,
    prune_storage,
    classify_screenshot_event,
    format_human_age,
    run_diagnostics,
)


class TestLeagueLoopDiagnostics(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.logs_dir = self.base / "logs"
        self.screenshots_dir = self.base / "debug_screenshots"
        self.sessions_dir = self.base / "sessions"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self.paths = {
            "base": self.base,
            "logs": self.logs_dir,
            "screenshots": self.screenshots_dir,
            "sessions": self.sessions_dir,
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

    def test_format_human_age(self):
        self.assertEqual(format_human_age(-5), "in the future")
        self.assertEqual(format_human_age(30), "30s ago")
        self.assertEqual(format_human_age(125), "2m ago")
        self.assertEqual(format_human_age(7200), "2.0h ago")
        self.assertEqual(format_human_age(172800), "2.0d ago")

    def test_inspect_screenshots_integrity_and_age(self):
        import time
        from datetime import datetime

        now = datetime(2026, 10, 15, 12, 0, 0)
        now_ts = now.timestamp()

        # Valid screenshot with content
        p1 = self.screenshots_dir / "20261015_115000_find_match_clicked.png"
        p1.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagecontent")
        os.utime(p1, (now_ts - 600, now_ts - 600))  # 10 minutes ago

        # Corrupted 0-byte screenshot
        p2 = self.screenshots_dir / "20261015_110000_tab_switch.png"
        p2.write_bytes(b"")
        os.utime(p2, (now_ts - 3600, now_ts - 3600))  # 1 hour ago

        captures = inspect_screenshots(self.screenshots_dir, max_count=5, now=now)
        self.assertEqual(len(captures), 2)

        # p1 should be intact and ~600s old
        c1 = next(c for c in captures if c["filename"] == p1.name)
        self.assertFalse(c1["is_corrupted"])
        self.assertEqual(c1["size_bytes"], len(b"\x89PNG\r\n\x1a\nfakeimagecontent"))
        self.assertEqual(c1["age_human"], "10m ago")

        # p2 should be corrupted
        c2 = next(c for c in captures if c["filename"] == p2.name)
        self.assertTrue(c2["is_corrupted"])
        self.assertEqual(c2["size_bytes"], 0)
        self.assertEqual(c2["age_human"], "1.0h ago")

    def test_inspect_screenshots_corrupted_flags_health(self):
        from datetime import datetime
        now = datetime(2026, 10, 15, 12, 0, 0)

        # Write clean logs
        self.paths["error_log"].write_text("INFO Clean", encoding="utf-8")
        self.paths["crash_log"].write_text("--- session 1 ---\n", encoding="utf-8")

        # 1 valid, 1 corrupted screenshot
        p1 = self.screenshots_dir / "20261015_115000_find_match_clicked.png"
        p1.write_bytes(b"content")
        p2 = self.screenshots_dir / "20261015_115500_tab_switch.png"
        p2.write_bytes(b"")

        diag = run_diagnostics(paths=self.paths, now=now)
        self.assertFalse(diag["healthy"])  # Must flag unhealthy due to corrupted screenshot!
        meta = diag["screenshot_analysis"]
        self.assertEqual(meta["corrupted_count"], 1)
        self.assertFalse(meta["all_intact"])

        # Fix corrupted screenshot
        p2.write_bytes(b"fixedcontent")
        diag_fixed = run_diagnostics(paths=self.paths, now=now)
        self.assertTrue(diag_fixed["healthy"])
        self.assertEqual(diag_fixed["screenshot_analysis"]["corrupted_count"], 0)
        self.assertTrue(diag_fixed["screenshot_analysis"]["all_intact"])

    def test_inspect_screenshots_staleness_threshold(self):
        from datetime import datetime
        now = datetime(2026, 10, 15, 12, 0, 0)
        now_ts = now.timestamp()

        # Screenshot modified 3 hours ago
        p = self.screenshots_dir / "20261015_090000_queue_action.png"
        p.write_bytes(b"content")
        os.utime(p, (now_ts - 10800, now_ts - 10800))

        # Check with max_age_hours=2.0 (should be stale)
        diag_stale = run_diagnostics(paths=self.paths, now=now, max_screenshot_age_hours=2.0)
        self.assertEqual(diag_stale["screenshot_analysis"]["stale_count"], 1)
        self.assertTrue(diag_stale["screenshot_analysis"]["captures"][0]["is_stale"])

        # Check with max_age_hours=4.0 (should not be stale)
        diag_fresh = run_diagnostics(paths=self.paths, now=now, max_screenshot_age_hours=4.0)
        self.assertEqual(diag_fresh["screenshot_analysis"]["stale_count"], 0)
        self.assertFalse(diag_fresh["screenshot_analysis"]["captures"][0]["is_stale"])

    def test_inspect_session_log_latency_and_stability_extraction(self):
        # 1. Clean log -> EXCELLENT
        self.paths["session_log"].write_text(
            '{"ts": "2026-10-14T10:00:00", "level": "INFO", "tag": "START", "msg": "Started"}\n',
            encoding="utf-8",
        )
        res_clean = inspect_session_log(self.paths["session_log"])
        self.assertEqual(res_clean["stability"]["rating"], "EXCELLENT")
        self.assertEqual(res_clean["stability"]["connection_drops_count"], 0)
        self.assertEqual(res_clean["stability"]["throttle_events_count"], 0)
        self.assertEqual(res_clean["latency_stats"]["count"], 0)

        # 2. Log with WS anomalies and drops -> DEGRADED
        entries = [
            '{"ts": "2026-10-14T10:00:00", "level": "WARNING", "tag": "LCU_WS_ANOMALY", "msg": "Latency anomaly detected on event: 150.00ms (threshold: 100.0ms)"}',
            '{"ts": "2026-10-14T10:00:01", "level": "WARNING", "tag": "LCU_WS_ANOMALY", "msg": "Latency anomaly detected on event: 250.00ms (threshold: 100.0ms)"}',
            '{"ts": "2026-10-14T10:00:02", "level": "INFO", "tag": "LCU_DIAGNOSTICS", "msg": "Connection drop recorded: WiFi to Ethernet flap (Total drops: 1)"}',
            '{"ts": "2026-10-14T10:00:03", "level": "WARNING", "tag": "LCU_NETWORK_THROTTLE", "msg": "Rapid connection drops detected (3 drops in 15s). Enabling network adapter reconnect rate throttling (backoff floor=5.0s)."}',
        ]
        self.paths["session_log"].write_text("\n".join(entries), encoding="utf-8")
        res_anomalies = inspect_session_log(self.paths["session_log"], max_entries=10)

        self.assertEqual(res_anomalies["stability"]["rating"], "DEGRADED")
        self.assertEqual(res_anomalies["stability"]["connection_drops_count"], 1)
        self.assertIn("WiFi to Ethernet flap", res_anomalies["stability"]["drop_reasons"])
        self.assertEqual(res_anomalies["stability"]["throttle_events_count"], 1)
        self.assertEqual(res_anomalies["throttle_events"][0]["backoff_floor"], 5.0)

        lat = res_anomalies["latency_stats"]
        self.assertEqual(lat["count"], 2)
        self.assertEqual(lat["min_ms"], 150.0)
        self.assertEqual(lat["max_ms"], 250.0)
        self.assertEqual(lat["avg_ms"], 200.0)

    def test_inspect_session_log_recovered_connection_drops(self):
        # Log with drop followed by successful reconnection -> RECOVERED
        entries = [
            '{"ts": "2026-10-14T10:00:00", "level": "INFO", "tag": "LCU_DIAGNOSTICS", "msg": "Connection drop recorded: Temporary socket disconnect (Total drops: 1)"}',
            '{"ts": "2026-10-14T10:00:02", "level": "INFO", "tag": "LCU_WS", "msg": "WebSocket connected."}',
        ]
        self.paths["session_log"].write_text("\n".join(entries), encoding="utf-8")
        res = inspect_session_log(self.paths["session_log"], max_entries=10)

        self.assertEqual(res["stability"]["rating"], "RECOVERED")
        self.assertEqual(res["stability"]["connection_drops_count"], 1)
        self.assertEqual(res["stability"]["recovered_drops_count"], 1)
        self.assertTrue(res["stability"]["is_connected"])
        self.assertTrue(res["connection_drops"][0]["recovered"])

    def test_main_cli_session_stability_display(self):
        from tools.leagueloop_diagnostics import main
        self.paths["error_log"].write_text("INFO Clean", encoding="utf-8")
        self.paths["crash_log"].write_text("--- session 1 ---\n", encoding="utf-8")
        self.paths["session_log"].write_text(
            '{"ts": "2026-10-14T10:00:00", "level": "WARNING", "tag": "LCU_WS_ANOMALY", "msg": "Latency anomaly detected on event: 180.00ms (threshold: 100.0ms)"}\n',
            encoding="utf-8",
        )

        with patch("sys.stdout"):
            with patch("tools.leagueloop_diagnostics.get_leagueloop_paths", return_value=self.paths):
                with patch("sys.argv", ["leagueloop_diagnostics.py", "--summary"]):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, 0)

    def test_inspect_saved_sessions_valid_and_missing(self):
        import json
        from datetime import datetime

        now = datetime(2026, 10, 15, 12, 0, 0)
        now_ts = now.timestamp()

        # Slot 1: valid account
        slot1 = self.sessions_dir / "user1"
        slot1.mkdir(parents=True, exist_ok=True)
        (slot1 / "session.json").write_text(
            json.dumps({"account_id": "user1", "captured_at": now_ts - 86400}),
            encoding="utf-8",
        )
        (slot1 / "RiotClientPrivateSettings.yaml").write_text("client: true\n", encoding="utf-8")
        (slot1 / "RiotGamesPrivateSettings.yaml").write_text("games: true\n", encoding="utf-8")

        # Slot 2: missing YAMLs
        slot2 = self.sessions_dir / "user2"
        slot2.mkdir(parents=True, exist_ok=True)
        (slot2 / "session.json").write_text(
            json.dumps({"account_id": "user2", "captured_at": now_ts - 100}),
            encoding="utf-8",
        )

        res = inspect_saved_sessions(self.sessions_dir, now=now)
        self.assertTrue(res["exists"])
        self.assertEqual(res["total_accounts"], 2)
        self.assertEqual(res["healthy_accounts"], 1)
        self.assertEqual(res["corrupted_accounts"], 1)

        acc1 = next(a for a in res["accounts"] if a["slot_name"] == "user1")
        self.assertFalse(acc1["is_corrupted"])
        self.assertEqual(acc1["age_days"], 1.0)
        self.assertEqual(acc1["age_human"], "1.0d ago")

        acc2 = next(a for a in res["accounts"] if a["slot_name"] == "user2")
        self.assertTrue(acc2["is_corrupted"])
        self.assertIn("RiotClientPrivateSettings.yaml", acc2["missing_files"])

    def test_inspect_saved_sessions_corrupted_manifest_or_yaml(self):
        # 0-byte manifest
        slot1 = self.sessions_dir / "corrupted_slot"
        slot1.mkdir(parents=True, exist_ok=True)
        (slot1 / "session.json").write_text("", encoding="utf-8")
        (slot1 / "RiotClientPrivateSettings.yaml").write_text("", encoding="utf-8")
        (slot1 / "RiotGamesPrivateSettings.yaml").write_text("", encoding="utf-8")

        res = inspect_saved_sessions(self.sessions_dir)
        self.assertEqual(res["total_accounts"], 1)
        self.assertEqual(res["corrupted_accounts"], 1)
        acc = res["accounts"][0]
        self.assertTrue(acc["is_corrupted"])
        self.assertTrue(any("0-byte" in f for f in acc["corrupted_files"]))

    def test_inspect_saved_sessions_staleness(self):
        import json
        from datetime import datetime

        now = datetime(2026, 10, 15, 12, 0, 0)
        now_ts = now.timestamp()

        slot = self.sessions_dir / "stale_user"
        slot.mkdir(parents=True, exist_ok=True)
        (slot / "session.json").write_text(
            json.dumps({"account_id": "stale_user", "captured_at": now_ts - (40 * 86400)}),
            encoding="utf-8",
        )
        (slot / "RiotClientPrivateSettings.yaml").write_text("client: true\n", encoding="utf-8")
        (slot / "RiotGamesPrivateSettings.yaml").write_text("games: true\n", encoding="utf-8")

        res = inspect_saved_sessions(self.sessions_dir, max_age_days=30.0, now=now)
        self.assertEqual(res["total_accounts"], 1)
        self.assertEqual(res["stale_accounts"], 1)
        self.assertTrue(res["accounts"][0]["is_stale"])
        self.assertFalse(res["accounts"][0]["is_corrupted"])

    def test_inspect_storage_usage_breakdown_and_warnings(self):
        # Add files in logs
        (self.logs_dir / "error.log").write_text("A" * 1024, encoding="utf-8")
        (self.logs_dir / "debug.log.1").write_text("B" * 2048, encoding="utf-8")

        # Add files in screenshots
        (self.screenshots_dir / "test.png").write_bytes(b"C" * 1024)

        # Add files in sessions
        slot = self.sessions_dir / "test_user"
        slot.mkdir(parents=True, exist_ok=True)
        (slot / "session.json").write_text("{}", encoding="utf-8")

        res = inspect_storage_usage(self.base, max_logs_mb=100.0, max_screenshots_mb=100.0)
        self.assertTrue(res["exists"])
        self.assertEqual(res["status"], "OPTIMAL")
        self.assertFalse(res["is_warning"])
        self.assertEqual(res["logs"]["file_count"], 2)
        self.assertEqual(res["logs"]["rotated_file_count"], 1)
        self.assertEqual(res["screenshots"]["file_count"], 1)
        self.assertEqual(res["sessions"]["slot_count"], 1)

        # Test warning trigger with tiny threshold
        res_warn = inspect_storage_usage(self.base, max_logs_mb=0.0001)
        self.assertTrue(res_warn["is_warning"])
        self.assertEqual(res_warn["status"], "WARNING")
        self.assertEqual(len(res_warn["warnings"]), 1)

    def test_run_diagnostics_saved_sessions_integration(self):
        import json
        self.paths["error_log"].write_text("INFO Clean", encoding="utf-8")
        self.paths["crash_log"].write_text("--- session 1 ---\n", encoding="utf-8")

        # Corrupted session slot
        slot = self.sessions_dir / "bad_slot"
        slot.mkdir(parents=True, exist_ok=True)
        (slot / "session.json").write_text("{bad json", encoding="utf-8")

        diag = run_diagnostics(paths=self.paths)
        self.assertFalse(diag["healthy"])
        self.assertEqual(diag["sessions_analysis"]["corrupted_accounts"], 1)

        # Fix corrupted session
        (slot / "session.json").write_text(json.dumps({"account_id": "good"}), encoding="utf-8")
        (slot / "RiotClientPrivateSettings.yaml").write_text("client: true\n", encoding="utf-8")
        (slot / "RiotGamesPrivateSettings.yaml").write_text("games: true\n", encoding="utf-8")

        diag_fixed = run_diagnostics(paths=self.paths)
        self.assertTrue(diag_fixed["healthy"])
        self.assertEqual(diag_fixed["sessions_analysis"]["corrupted_accounts"], 0)

    def test_main_cli_sessions_and_storage_display(self):
        from tools.leagueloop_diagnostics import main
        import json
        self.paths["error_log"].write_text("INFO Clean", encoding="utf-8")
        self.paths["crash_log"].write_text("--- session 1 ---\n", encoding="utf-8")

        slot = self.sessions_dir / "user_cli"
        slot.mkdir(parents=True, exist_ok=True)
        (slot / "session.json").write_text(json.dumps({"account_id": "user_cli"}), encoding="utf-8")
        (slot / "RiotClientPrivateSettings.yaml").write_text("client: true\n", encoding="utf-8")
        (slot / "RiotGamesPrivateSettings.yaml").write_text("games: true\n", encoding="utf-8")

        with patch("sys.stdout"):
            with patch("tools.leagueloop_diagnostics.get_leagueloop_paths", return_value=self.paths):
                with patch("sys.argv", ["leagueloop_diagnostics.py", "--summary"]):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, 0)

    def test_prune_storage_dry_run_preserves_files(self):
        # Active logs
        self.paths["error_log"].write_text("ERROR err\n", encoding="utf-8")
        self.paths["crash_log"].write_text("crash\n", encoding="utf-8")
        self.paths["debug_log"].write_text("debug\n", encoding="utf-8")
        self.paths["session_log"].write_text("session\n", encoding="utf-8")

        # Rotated logs
        rot1 = self.logs_dir / "debug.log.1"
        rot2 = self.logs_dir / "error.log.1"
        rot3 = self.logs_dir / "session.jsonl.2"
        rot1.write_text("rot1" * 100, encoding="utf-8")
        rot2.write_text("rot2" * 100, encoding="utf-8")
        rot3.write_text("rot3" * 100, encoding="utf-8")

        # Screenshots
        base_time = 1000000.0
        sc_files = []
        for i in range(5):
            sc = self.screenshots_dir / f"20261014_10000{i}_test.png"
            sc.write_text("png_bytes" * 50, encoding="utf-8")
            os.utime(sc, (base_time + i * 10, base_time + i * 10))
            sc_files.append(sc)

        res = prune_storage(
            self.base,
            dry_run=True,
            max_screenshots_keep=2,
            prune_rotated_logs=True,
        )

        self.assertTrue(res["dry_run"])
        self.assertGreater(res["logs_pruned"]["bytes"], 0)
        self.assertGreater(res["screenshots_pruned"]["bytes"], 0)
        self.assertGreaterEqual(res["total_freed_mb"], 0.0)

        # Confirm all files still exist because dry_run=True
        self.assertTrue(rot1.exists())
        self.assertTrue(rot2.exists())
        self.assertTrue(rot3.exists())
        for sc in sc_files:
            self.assertTrue(sc.exists())

    def test_prune_storage_execution_deletes_rotated_and_preserves_active(self):
        # Active logs
        self.paths["error_log"].write_text("ERROR err\n", encoding="utf-8")
        self.paths["crash_log"].write_text("crash\n", encoding="utf-8")
        self.paths["debug_log"].write_text("debug\n", encoding="utf-8")
        self.paths["session_log"].write_text("session\n", encoding="utf-8")

        # Rotated logs
        rot1 = self.logs_dir / "debug.log.1"
        rot2 = self.logs_dir / "error.log.1"
        rot1.write_text("rot1", encoding="utf-8")
        rot2.write_text("rot2", encoding="utf-8")

        # Screenshots
        base_time = 1000000.0
        sc_files = []
        for i in range(4):
            sc = self.screenshots_dir / f"20261014_10000{i}_test.png"
            sc.write_text("png", encoding="utf-8")
            os.utime(sc, (base_time + i * 10, base_time + i * 10))
            sc_files.append(sc)

        res = prune_storage(
            self.base,
            dry_run=False,
            max_screenshots_keep=2,
            prune_rotated_logs=True,
        )

        self.assertFalse(res["dry_run"])
        self.assertEqual(res["logs_pruned"]["count"], 2)
        self.assertEqual(res["screenshots_pruned"]["count"], 2)

        # Active logs MUST still exist
        self.assertTrue(self.paths["error_log"].exists())
        self.assertTrue(self.paths["crash_log"].exists())
        self.assertTrue(self.paths["debug_log"].exists())
        self.assertTrue(self.paths["session_log"].exists())

        # Rotated logs MUST be deleted
        self.assertFalse(rot1.exists())
        self.assertFalse(rot2.exists())

        # Oldest screenshots deleted, newest 2 kept
        self.assertFalse(sc_files[0].exists())
        self.assertFalse(sc_files[1].exists())
        self.assertTrue(sc_files[2].exists())
        self.assertTrue(sc_files[3].exists())

    def test_prune_storage_keep_rotated_logs(self):
        rot1 = self.logs_dir / "debug.log.1"
        rot1.write_text("rot1", encoding="utf-8")

        res = prune_storage(
            self.base,
            dry_run=False,
            prune_rotated_logs=False,
        )

        self.assertEqual(res["logs_pruned"]["count"], 0)
        self.assertTrue(rot1.exists())

    def test_main_cli_prune_storage_execution(self):
        from tools.leagueloop_diagnostics import main
        rot = self.logs_dir / "debug.log.1"
        rot.write_text("rot", encoding="utf-8")
        self.paths["error_log"].write_text("INFO Clean", encoding="utf-8")

        with patch("sys.stdout"):
            with patch("tools.leagueloop_diagnostics.get_leagueloop_paths", return_value=self.paths):
                with patch("sys.argv", ["leagueloop_diagnostics.py", "--prune-storage", "--dry-run"]):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, 0)
        self.assertTrue(rot.exists())


if __name__ == "__main__":
    unittest.main()

