import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from tools.autonomous_improvement_runner import (
    measure_codebase_metrics,
    run_diagnostics_check,
    run_version_alignment_check,
    run_build_assets_check,
    run_build_health_check,
    run_accounts_check,
    run_silent_excepts_check,
    run_entropy_check,
    run_tests_check,
    update_memory_state,
    run_loop,
)


class TestAutonomousImprovementRunner(unittest.TestCase):
    def test_measure_codebase_metrics(self):
        metrics = measure_codebase_metrics()
        self.assertIn("total_py_files", metrics)
        self.assertIn("total_py_lines", metrics)
        self.assertIn("breakdown", metrics)
        self.assertIn("test_to_code_ratio", metrics)
        self.assertGreater(metrics["total_py_files"], 0)
        self.assertGreater(metrics["total_py_lines"], 0)
        self.assertIn("src", metrics["breakdown"])
        self.assertIn("tests", metrics["breakdown"])
        self.assertIn("tools", metrics["breakdown"])
        self.assertIsInstance(metrics["test_to_code_ratio"], float)

    @patch("tools.leagueloop_diagnostics.run_diagnostics")
    def test_run_diagnostics_check(self, mock_diag):
        mock_diag.return_value = {"healthy": True, "error_analysis": {}}
        diag = run_diagnostics_check()
        self.assertTrue(diag["healthy"])

    @patch("tools.bump_version.check_version_alignment")
    def test_run_version_alignment_check(self, mock_align):
        mock_align.return_value = (True, "Versions aligned")
        res = run_version_alignment_check()
        self.assertTrue(res["aligned"])
        self.assertEqual(res["message"], "Versions aligned")

    @patch("tools.build_validator.validate_files")
    def test_run_build_assets_check(self, mock_validate):
        mock_validate.return_value = True
        res = run_build_assets_check()
        self.assertTrue(res["ready"])
        self.assertIn("present", res["message"])

        mock_validate.return_value = False
        res_fail = run_build_assets_check()
        self.assertFalse(res_fail["ready"])
        self.assertIn("Missing", res_fail["message"])

    @patch("tools.build_validator.verify_system_wide_health")
    def test_run_build_health_check(self, mock_health):
        mock_health.return_value = {"status": "HEALTHY", "version": "2-10-289-1636", "duration_ms": 3.5}
        health = run_build_health_check()
        self.assertEqual(health["status"], "HEALTHY")
        self.assertEqual(health["version"], "2-10-289-1636")

    @patch("tools.check_accounts.run_account_preflight")
    def test_run_accounts_check(self, mock_accts):
        mock_accts.return_value = {"status": "HEALTHY", "problems_count": 0, "accounts_count": 4}
        res = run_accounts_check()
        self.assertEqual(res["status"], "HEALTHY")
        self.assertEqual(res["problems_count"], 0)
        self.assertEqual(res["accounts_count"], 4)

    @patch("tools.log_silent_excepts.scan_silent_handlers")
    def test_run_silent_excepts_check(self, mock_scan):
        mock_scan.return_value = {
            "status": "PASS",
            "silent_handlers_count": 0,
            "files_audited": 92,
            "offending_files": [],
            "message": "Zero silent exception handlers detected",
        }
        res = run_silent_excepts_check()
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["silent_handlers_count"], 0)
        self.assertEqual(res["files_audited"], 92)

    @patch("tools.log_silent_excepts.scan_silent_handlers")
    def test_run_silent_excepts_check_failure(self, mock_scan):
        mock_scan.return_value = {
            "status": "FAIL",
            "silent_handlers_count": 2,
            "files_audited": 92,
            "offending_files": [{"file": "src/services/bad.py", "count": 2, "sites": []}],
            "message": "2 silent handler(s) detected across 1 file(s)",
        }
        res = run_silent_excepts_check()
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["silent_handlers_count"], 2)

    @patch("tools.code_entropy_analyzer.get_top_entropy_files")
    @patch("tools.code_entropy_analyzer.run_entropy_summary")
    def test_run_entropy_check(self, mock_entropy, mock_top):
        mock_entropy.return_value = {"status": "PASS", "avg_entropy": 12.5, "bare_excepts_total": 0}
        mock_top.return_value = [{"file": "src/services/automation.py", "entropy_score": 800}]
        entropy = run_entropy_check()
        self.assertEqual(entropy["status"], "PASS")
        self.assertEqual(len(entropy["top_files"]), 1)

    @patch("subprocess.run")
    def test_run_tests_check_multi_match_parsing(self, mock_subproc):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = (
            "Progress: 50 passed\n"
            "Progress: 200 passed\n"
            "965 passed, 22 subtests passed, 2 skipped in 18.62s\n"
        )
        mock_proc.stderr = ""
        mock_subproc.return_value = mock_proc

        res = run_tests_check(run_all=True)
        self.assertEqual(res["passed"], 965)
        self.assertEqual(res["skipped"], 2)
        self.assertEqual(res["failed"], 0)
        self.assertEqual(res["errors"], 0)
        self.assertTrue(res["success"])

    @patch("subprocess.run")
    def test_run_tests_check_error_summary_parsing(self, mock_subproc):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = (
            "Progress: 10 passed\n"
            "5 passed, 1 failed, 2 errors in 3.12s\n"
        )
        mock_proc.stderr = ""
        mock_subproc.return_value = mock_proc

        res = run_tests_check(run_all=False)
        self.assertEqual(res["passed"], 5)
        self.assertEqual(res["failed"], 1)
        self.assertEqual(res["errors"], 2)
        self.assertFalse(res["success"])

    @patch("subprocess.run")
    def test_run_tests_check_unparsed_failure_fallback(self, mock_subproc):
        mock_proc = MagicMock()
        mock_proc.returncode = 2
        mock_proc.stdout = "INTERNALERROR: pytest encountered an unhandled exception\n"
        mock_proc.stderr = ""
        mock_subproc.return_value = mock_proc

        res = run_tests_check(run_all=False)
        self.assertEqual(res["passed"], 0)
        self.assertEqual(res["failed"], 0)
        self.assertEqual(res["errors"], 1)
        self.assertFalse(res["success"])

    def test_update_memory_state_dry_run(self):
        metrics = {
            "total_py_files": 150,
            "total_py_lines": 45000,
            "breakdown": {"src": {"files": 80, "lines": 30000}, "tests": {"files": 50, "lines": 10000}},
            "test_to_code_ratio": 0.333,
        }
        tests = {"passed": 787, "failed": 0, "duration_seconds": 17.5}
        entropy = {"status": "PASS", "avg_entropy": 42.0, "bare_excepts_total": 0}
        storage = {"status": "OPTIMAL", "total_mb": 45.2, "logs": {"total_mb": 12.0}, "screenshots": {"total_mb": 33.2}, "warnings": []}
        result = update_memory_state(
            metrics,
            tests,
            dry_run=True,
            semantic_learnings=[{"concept": "Test Concept", "description": "Desc"}],
            procedural_methods=[{"method": "Test Method", "procedure": ["Step 1"]}],
            entropy_results=entropy,
            storage_results=storage,
        )

        self.assertFalse(result["persisted"])
        self.assertIn("new_state", result)
        self.assertEqual(result["new_state"]["test_baseline"]["passed"], 787)
        self.assertEqual(result["new_state"]["test_baseline"]["errors"], 0)
        self.assertEqual(result["new_state"]["index_baseline"]["total_files"], 150)
        self.assertEqual(result["new_state"]["entropy_baseline"]["avg_entropy"], 42.0)
        self.assertEqual(result["new_state"]["index_baseline"]["test_to_code_ratio"], 0.333)
        self.assertEqual(result["new_state"]["storage_baseline"]["total_mb"], 45.2)
        self.assertEqual(result["new_state"]["storage_baseline"]["status"], "OPTIMAL")
        self.assertEqual(len(result["semantic_learnings"]), 1)
        self.assertEqual(len(result["procedural_methods"]), 1)

    def test_update_memory_state_targeted_preserves_baseline(self):
        metrics = {"total_py_files": 150, "total_py_lines": 45000, "test_to_code_ratio": 0.33}
        tests = {"run_all": False, "passed": 11, "failed": 0, "skipped": 0, "duration_seconds": 0.8}
        
        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data='{"run_number": 146, "test_baseline": {"passed": 966, "failed": 0, "errors": 0}}')):
            result = update_memory_state(metrics, tests, dry_run=True)
            
        self.assertEqual(result["new_state"]["test_baseline"]["passed"], 966)
        self.assertEqual(result["new_state"]["test_baseline"]["last_targeted_passed"], 11)
        self.assertEqual(result["new_state"]["test_baseline"]["skipped"], 0)

    def test_update_memory_state_full_suite_updates_baseline(self):
        metrics = {"total_py_files": 150, "total_py_lines": 45000, "test_to_code_ratio": 0.33}
        tests = {"run_all": True, "passed": 970, "failed": 0, "skipped": 2, "duration_seconds": 18.2}
        
        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data='{"run_number": 146, "test_baseline": {"passed": 966, "failed": 0, "errors": 0}}')):
            result = update_memory_state(metrics, tests, dry_run=True)
            
        self.assertEqual(result["new_state"]["test_baseline"]["passed"], 970)
        self.assertEqual(result["new_state"]["test_baseline"]["last_targeted_passed"], 0)
        self.assertEqual(result["new_state"]["test_baseline"]["skipped"], 2)

    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_entropy_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    @patch("tools.autonomous_improvement_runner.sync_mempalace")
    def test_run_loop_dry_run(self, mock_mempalace, mock_tests, mock_entropy, mock_diag):
        mock_diag.return_value = {"healthy": True}
        mock_entropy.return_value = {"status": "PASS", "avg_entropy": 15.0, "bare_excepts_total": 0}
        mock_tests.return_value = {
            "exit_code": 0,
            "success": True,
            "duration_seconds": 1.5,
            "passed": 787,
            "failed": 0,
            "skipped": 5,
        }

        res = run_loop(all_tests=False, dry_run=True)
        self.assertIn("loop_number", res)
        self.assertTrue(res["diagnostics"]["healthy"])
        self.assertEqual(res["entropy"]["status"], "PASS")
        self.assertTrue(res["tests"]["success"])
        self.assertFalse(res["memory"]["persisted"])
        mock_mempalace.assert_not_called()

    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_entropy_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    @patch("tools.autonomous_improvement_runner.sync_mempalace")
    def test_run_loop_feature_optimization(self, mock_mempalace, mock_tests, mock_entropy, mock_diag):
        mock_diag.return_value = {"healthy": True}
        mock_entropy.return_value = {"status": "PASS", "avg_entropy": 10.0, "bare_excepts_total": 0}
        mock_tests.return_value = {
            "exit_code": 0,
            "success": True,
            "duration_seconds": 1.0,
            "passed": 807,
            "failed": 0,
            "skipped": 0,
        }

        res = run_loop(
            all_tests=False,
            dry_run=True,
            feature="Dynamic Delta Baseline",
            impact="Tracks baseline deltas cleanly across runs.",
        )
        self.assertEqual(res["tests"]["passed"], 807)

    @patch("tools.autonomous_improvement_runner.run_accounts_check")
    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_entropy_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    @patch("tools.autonomous_improvement_runner.sync_mempalace")
    def test_run_loop_includes_accounts_preflight_action(
        self, mock_mempalace, mock_tests, mock_entropy, mock_diag, mock_accts
    ):
        mock_diag.return_value = {"healthy": True}
        mock_entropy.return_value = {"status": "PASS", "avg_entropy": 10.0, "bare_excepts_total": 0}
        mock_tests.return_value = {
            "exit_code": 0,
            "success": True,
            "duration_seconds": 1.0,
            "passed": 807,
            "failed": 0,
            "skipped": 0,
        }
        mock_accts.return_value = {
            "status": "HEALTHY",
            "problems_count": 0,
            "accounts_count": 4,
            "usable_sessions_count": 2,
            "current_user": "themalcolm3",
        }

        res = run_loop(all_tests=False, dry_run=True)
        actions = res["memory"]["episodic_entry"]["actions"]
        acct_action = [a for a in actions if "Account switching preflight" in a]
        self.assertEqual(len(acct_action), 1)
        self.assertIn("HEALTHY", acct_action[0])
        self.assertIn("4 accounts", acct_action[0])
        self.assertIn("2 usable sessions", acct_action[0])

    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_entropy_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    @patch("tools.autonomous_improvement_runner.sync_mempalace")
    def test_run_loop_warning_categories_telemetry(self, mock_mempalace, mock_tests, mock_entropy, mock_diag):
        mock_diag.return_value = {
            "healthy": True,
            "error_analysis": {
                "recent_warnings": ["warn1", "warn2"],
                "warning_categories": {"lcu_telemetry": 1, "riot_client_api": 1},
            },
        }
        mock_entropy.return_value = {"status": "PASS", "avg_entropy": 10.0, "bare_excepts_total": 0}
        mock_tests.return_value = {
            "exit_code": 0,
            "success": True,
            "duration_seconds": 1.0,
            "passed": 807,
            "failed": 0,
            "skipped": 0,
        }

        res = run_loop(all_tests=False, dry_run=True)
        actions = res["memory"]["episodic_entry"]["actions"]
        diag_action = [a for a in actions if "Verified runtime logs" in a]
        self.assertEqual(len(diag_action), 1)
        self.assertIn("2 warnings", diag_action[0])
        self.assertIn("lcu_telemetry", diag_action[0])

    @patch("tools.autonomous_improvement_runner.run_silent_excepts_check")
    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_entropy_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    @patch("tools.autonomous_improvement_runner.sync_mempalace")
    def test_run_loop_includes_silent_excepts_action(
        self, mock_mempalace, mock_tests, mock_entropy, mock_diag, mock_silent
    ):
        mock_diag.return_value = {"healthy": True}
        mock_entropy.return_value = {"status": "PASS", "avg_entropy": 10.0, "bare_excepts_total": 0}
        mock_tests.return_value = {
            "exit_code": 0,
            "success": True,
            "duration_seconds": 1.0,
            "passed": 807,
            "failed": 0,
            "skipped": 0,
        }
        mock_silent.return_value = {
            "status": "PASS",
            "silent_handlers_count": 0,
            "files_audited": 92,
            "offending_files": [],
            "message": "Zero silent exception handlers detected",
        }

        res = run_loop(all_tests=False, dry_run=True)
        actions = res["memory"]["episodic_entry"]["actions"]
        silent_action = [a for a in actions if "Swallowed exceptions audit" in a]
        self.assertEqual(len(silent_action), 1)
        self.assertIn("PASS", silent_action[0])
        self.assertIn("0 swallowed exceptions", silent_action[0])
        self.assertEqual(res["silent_excepts"]["status"], "PASS")
        self.assertEqual(res["silent_excepts"]["silent_handlers_count"], 0)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 98,
            "diagnostics": {"healthy": True},
            "metrics": {"total_py_files": 174, "total_py_lines": 50000},
            "entropy": {"status": "PASS", "avg_entropy": 10.0, "bare_excepts_total": 0},
            "tests": {"passed": 807, "failed": 0, "duration_seconds": 1.2, "success": True},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }

        with patch("sys.stdout") as mock_stdout:
            with self.assertRaises(SystemExit) as cm:
                main(["--dry-run"])
            self.assertEqual(cm.exception.code, 0)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_prune_storage(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 99,
            "diagnostics": {"healthy": True, "storage_analysis": {"exists": True, "status": "OPTIMAL", "total_mb": 50.0, "logs": {"total_mb": 10.0}, "screenshots": {"total_mb": 40.0}}},
            "metrics": {"total_py_files": 174, "total_py_lines": 50000},
            "entropy": {"status": "PASS", "avg_entropy": 10.0, "bare_excepts_total": 0},
            "tests": {"passed": 807, "failed": 0, "duration_seconds": 1.2, "success": True},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
            "prune_results": {
                "dry_run": False,
                "total_freed_mb": 120.5,
                "logs_pruned": {"mb": 50.0, "count": 3},
                "screenshots_pruned": {"mb": 70.5, "count": 100},
            },
        }

        with patch("sys.stdout") as mock_stdout:
            with self.assertRaises(SystemExit) as cm:
                main(["--prune-storage"])
            self.assertEqual(cm.exception.code, 0)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_prune_storage_with_max_screenshots_keep(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 100,
            "diagnostics": {"healthy": True},
            "metrics": {"total_py_files": 174, "total_py_lines": 50000},
            "entropy": {"status": "PASS", "avg_entropy": 10.0, "bare_excepts_total": 0},
            "tests": {"passed": 807, "failed": 0, "duration_seconds": 1.2, "success": True},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }

        with patch("sys.stdout") as mock_stdout:
            with self.assertRaises(SystemExit) as cm:
                main(["--prune-storage", "--max-screenshots-keep", "50"])
            self.assertEqual(cm.exception.code, 0)
            mock_run_loop.assert_called_once_with(
                all_tests=False,
                targets=None,
                staged=False,
                dry_run=False,
                feature=None,
                impact=None,
                prune_storage_flag=True,
                max_screenshots_keep=50,
                max_screenshot_age_days=None,
            )

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_prune_storage_with_max_screenshot_age_days(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 100,
            "diagnostics": {"healthy": True},
            "metrics": {"total_py_files": 174, "total_py_lines": 50000},
            "entropy": {"status": "PASS", "avg_entropy": 10.0, "bare_excepts_total": 0},
            "tests": {"passed": 807, "failed": 0, "duration_seconds": 1.2, "success": True},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }

        with patch("sys.stdout") as mock_stdout:
            with self.assertRaises(SystemExit) as cm:
                main(["--prune-storage", "--max-screenshot-age-days", "7.5"])
            self.assertEqual(cm.exception.code, 0)
            mock_run_loop.assert_called_once_with(
                all_tests=False,
                targets=None,
                staged=False,
                dry_run=False,
                feature=None,
                impact=None,
                prune_storage_flag=True,
                max_screenshots_keep=None,
                max_screenshot_age_days=7.5,
            )

    @patch("tools.leagueloop_diagnostics.prune_storage")
    @patch("tools.autonomous_improvement_runner.run_silent_excepts_check")
    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_entropy_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    @patch("tools.autonomous_improvement_runner.sync_mempalace")
    def test_run_loop_passes_max_screenshots_keep(
        self, mock_mempalace, mock_tests, mock_entropy, mock_diag, mock_silent, mock_prune
    ):
        mock_diag.return_value = {"healthy": True}
        mock_entropy.return_value = {"status": "PASS", "avg_entropy": 10.0, "bare_excepts_total": 0}
        mock_tests.return_value = {"exit_code": 0, "success": True, "duration_seconds": 1.0, "passed": 807, "failed": 0, "skipped": 0}
        mock_silent.return_value = {"status": "PASS", "silent_handlers_count": 0, "files_audited": 92}
        mock_prune.return_value = {"total_freed_mb": 50.0, "logs_pruned": {"mb": 0.0}, "screenshots_pruned": {"mb": 50.0}}

        res = run_loop(prune_storage_flag=True, max_screenshots_keep=75, dry_run=True)
        self.assertIsNotNone(res.get("prune_results"))
        mock_prune.assert_called_once()
        args, kwargs = mock_prune.call_args
        self.assertEqual(kwargs.get("max_screenshots_keep"), 75)
        self.assertTrue(kwargs.get("dry_run"))

    @patch("tools.leagueloop_diagnostics.prune_storage")
    @patch("tools.autonomous_improvement_runner.run_silent_excepts_check")
    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_entropy_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    @patch("tools.autonomous_improvement_runner.sync_mempalace")
    def test_run_loop_passes_max_screenshot_age_days(
        self, mock_mempalace, mock_tests, mock_entropy, mock_diag, mock_silent, mock_prune
    ):
        mock_diag.return_value = {"healthy": True}
        mock_entropy.return_value = {"status": "PASS", "avg_entropy": 10.0, "bare_excepts_total": 0}
        mock_tests.return_value = {"exit_code": 0, "success": True, "duration_seconds": 1.0, "passed": 807, "failed": 0, "skipped": 0}
        mock_silent.return_value = {"status": "PASS", "silent_handlers_count": 0, "files_audited": 92}
        mock_prune.return_value = {"total_freed_mb": 50.0, "logs_pruned": {"mb": 0.0}, "screenshots_pruned": {"mb": 50.0}}

        res = run_loop(prune_storage_flag=True, max_screenshot_age_days=10.0, dry_run=True)
        self.assertIsNotNone(res.get("prune_results"))
        mock_prune.assert_called_once()
        args, kwargs = mock_prune.call_args
        self.assertEqual(kwargs.get("max_screenshot_age_days"), 10.0)
        self.assertTrue(kwargs.get("dry_run"))

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_main_cli_check_baseline(self, mock_read, mock_exists):
        from tools.autonomous_improvement_runner import main
        mock_exists.return_value = True
        mock_read.return_value = '{"run_number": 109, "test_baseline": {"passed": 24}}'

        with patch("sys.stdout") as mock_stdout:
            with self.assertRaises(SystemExit) as cm:
                main(["--check-baseline"])
            self.assertEqual(cm.exception.code, 0)

    @patch("subprocess.run")
    def test_run_tests_check_targets_and_staged(self, mock_subproc):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "4 passed in 0.25s\n"
        mock_proc.stderr = ""
        mock_subproc.return_value = mock_proc

        res = run_tests_check(run_all=False, targets=["tests/test_fast_test_runner.py"], staged=True)
        self.assertEqual(res["passed"], 4)
        self.assertEqual(res["targets"], ["tests/test_fast_test_runner.py"])
        self.assertTrue(res["staged"])
        self.assertTrue(res["success"])

        args, kwargs = mock_subproc.call_args
        cmd = args[0]
        self.assertIn("--staged", cmd)
        self.assertIn("tests/test_fast_test_runner.py", cmd)
        self.assertNotIn("--all", cmd)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_targets_and_staged(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 150,
            "diagnostics": {"healthy": True},
            "metrics": {"total_py_files": 185, "total_py_lines": 54800},
            "entropy": {"status": "PASS", "avg_entropy": 67.0, "bare_excepts_total": 0},
            "tests": {
                "passed": 12,
                "failed": 0,
                "duration_seconds": 0.4,
                "success": True,
                "run_all": False,
                "staged": True,
                "targets": ["tests/test_fast_test_runner.py"],
            },
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }

        with patch("sys.stdout") as mock_stdout:
            with self.assertRaises(SystemExit) as cm:
                main(["tests/test_fast_test_runner.py", "--staged"])
            self.assertEqual(cm.exception.code, 0)
            mock_run_loop.assert_called_once_with(
                all_tests=False,
                targets=["tests/test_fast_test_runner.py"],
                staged=True,
                dry_run=False,
                feature=None,
                impact=None,
                prune_storage_flag=False,
                max_screenshots_keep=None,
                max_screenshot_age_days=None,
            )

    @patch("subprocess.run")
    def test_run_tests_check_warning_summary_parsing(self, mock_subproc):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "965 passed, 4 warnings in 10.5s\n"
        mock_proc.stderr = ""
        mock_subproc.return_value = mock_proc

        res = run_tests_check(run_all=True)
        self.assertEqual(res["passed"], 965)
        self.assertEqual(res["warnings"], 4)
        self.assertTrue(res["success"])

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_unknown_flags_forwarding(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 150,
            "diagnostics": {"healthy": True},
            "metrics": {"total_py_files": 185, "total_py_lines": 54800},
            "entropy": {"status": "PASS", "avg_entropy": 67.0, "bare_excepts_total": 0},
            "tests": {
                "passed": 5,
                "failed": 0,
                "warnings": 1,
                "duration_seconds": 0.2,
                "success": True,
                "run_all": False,
                "staged": False,
                "targets": ["-k", "test_ast", "-x"],
            },
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }

        with patch("sys.stdout"):
            with self.assertRaises(SystemExit) as cm:
                main(["-k", "test_ast", "-x"])
            self.assertEqual(cm.exception.code, 0)
            mock_run_loop.assert_called_once_with(
                all_tests=False,
                targets=["-k", "test_ast", "-x"],
                staged=False,
                dry_run=False,
                feature=None,
                impact=None,
                prune_storage_flag=False,
                max_screenshots_keep=None,
                max_screenshot_age_days=None,
            )


    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_sync_mempalace_success(self, mock_exists, mock_subproc):
        from tools.autonomous_improvement_runner import sync_mempalace
        mock_exists.return_value = True
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_subproc.return_value = mock_proc

        result = sync_mempalace(164, "Diagnostics: HEALTHY. Test baseline: 982 passed.")
        self.assertTrue(result)
        mock_subproc.assert_called_once()
        args, kwargs = mock_subproc.call_args
        cmd = args[0]
        self.assertIn("diary", cmd)
        self.assertIn("write", cmd)
        self.assertIn("Run #164", cmd[-1])
        self.assertIn("PROJ:LeagueLoop.DEV", cmd[-1])
        self.assertIn("★★★", cmd[-1])

    @patch("shutil.which")
    @patch("pathlib.Path.exists")
    def test_sync_mempalace_exe_not_found(self, mock_exists, mock_which):
        from tools.autonomous_improvement_runner import sync_mempalace
        mock_exists.return_value = False
        mock_which.return_value = None

        result = sync_mempalace(164, "Summary")
        self.assertFalse(result)

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("pathlib.Path.exists")
    def test_sync_mempalace_shutil_which_fallback(self, mock_exists, mock_which, mock_subproc):
        from tools.autonomous_improvement_runner import sync_mempalace
        mock_exists.return_value = True
        mock_which.return_value = "C:\\Tools\\mempalace.exe"
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_subproc.return_value = mock_proc

        result = sync_mempalace(164, "Summary text")
        self.assertTrue(result)

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_sync_mempalace_subprocess_failure(self, mock_exists, mock_subproc):
        from tools.autonomous_improvement_runner import sync_mempalace
        mock_exists.return_value = True
        mock_subproc.side_effect = OSError("Execution failed")

        result = sync_mempalace(164, "Summary")
        self.assertFalse(result)

    @patch("builtins.open", new_callable=mock_open)
    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_sync_mempalace_inbox_staging_fallback(self, mock_exists, mock_subproc, mock_file):
        from tools.autonomous_improvement_runner import sync_mempalace
        mock_exists.return_value = True
        mock_proc = MagicMock()
        mock_proc.returncode = 1  # CLI returns error (e.g. invalid 'diary' subcommand)
        mock_subproc.return_value = mock_proc

        result = sync_mempalace(164, "Summary text")
        self.assertTrue(result)
        mock_subproc.assert_called_once()
        self.assertEqual(mock_subproc.call_args[1].get("timeout"), 10)
        mock_file.assert_called_once()
        handle = mock_file()
        written = "".join(call[0][0] for call in handle.write.call_args_list)
        self.assertIn("Run #164", written)
        self.assertIn("Summary text", written)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_verbose_flag(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 278,
            "diagnostics": {"healthy": True},
            "metrics": {"total_py_files": 213, "total_py_lines": 63600},
            "entropy": {
                "status": "WARN",
                "avg_entropy": 67.16,
                "bare_excepts_total": 0,
                "top_files": [
                    {"file": "src/services/automation.py", "entropy_score": 827, "cyclomatic_complexity": 376}
                ],
            },
            "tests": {"passed": 1239, "failed": 0, "duration_seconds": 12.5, "success": True},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }

        with patch("sys.stdout") as mock_stdout:
            with self.assertRaises(SystemExit) as cm:
                main(["-v", "--dry-run"])
            self.assertEqual(cm.exception.code, 0)

        # Verify verbose flag was passed to run_loop
        self.assertTrue(mock_run_loop.call_args[1].get("verbose"))

    @patch("subprocess.run")
    def test_run_tests_check_timeout_handling(self, mock_subproc):
        import subprocess
        mock_subproc.side_effect = subprocess.TimeoutExpired(cmd=["pytest"], timeout=180.0)
        res = run_tests_check(run_all=False, timeout=180.0)
        self.assertFalse(res["success"])
        self.assertEqual(res["exit_code"], -1)
        self.assertEqual(res["errors"], 1)
        self.assertIn("timed out after 180.0s", res["raw_output"])

    def test_update_memory_state_warning_baseline(self):
        diag_mock = {
            "error_analysis": {
                "recent_warnings": ["WARNING [AccountSwitch] captcha"],
                "warning_categories": {"account_switch": 1},
            }
        }
        res = update_memory_state(
            metrics={"total_py_files": 10, "total_py_lines": 500, "breakdown": {}, "test_to_code_ratio": 0.5},
            test_results={"passed": 5, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False},
            dry_run=True,
            diagnostics_results=diag_mock,
        )
        wb = res["new_state"].get("warning_baseline", {})
        self.assertEqual(wb.get("status"), "WARN")
        self.assertEqual(wb.get("total_warnings"), 1)
        self.assertEqual(wb.get("categories"), {"account_switch": 1})

    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    def test_run_loop_with_warning_category(self, mock_tests, mock_diag):
        mock_diag.return_value = {"healthy": True, "error_analysis": {"recent_warnings": [], "warning_categories": {}}}
        mock_tests.return_value = {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False, "success": True}
        res = run_loop(dry_run=True, warning_category="lcu_telemetry", test_timeout=60.0)
        mock_diag.assert_called_once_with(category="lcu_telemetry", screenshot_category=None, error_category=None, crash_category=None)
        mock_tests.assert_called_once()
        self.assertEqual(mock_tests.call_args[1].get("timeout"), 60.0)


    def test_update_memory_state_screenshot_baseline(self):
        diag_mock = {
            "error_analysis": {"recent_warnings": [], "warning_categories": {}},
            "screenshot_analysis": {
                "total_returned": 5,
                "all_intact": True,
                "corrupted_count": 0,
                "stale_count": 0,
                "category_counts": {"game_phase_change": 5},
                "newest_age_human": "2.5h ago",
            },
        }
        res = update_memory_state(
            metrics={"total_py_files": 10, "total_py_lines": 500, "breakdown": {}, "test_to_code_ratio": 0.5},
            test_results={"passed": 5, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False},
            dry_run=True,
            diagnostics_results=diag_mock,
        )
        sb = res["new_state"].get("screenshot_baseline", {})
        self.assertEqual(sb.get("status"), "OPTIMAL")
        self.assertEqual(sb.get("total_captures"), 5)
        self.assertEqual(sb.get("corrupted_count"), 0)
        self.assertEqual(sb.get("category_counts"), {"game_phase_change": 5})

    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    def test_run_loop_with_screenshot_category(self, mock_tests, mock_diag):
        mock_diag.return_value = {"healthy": True, "error_analysis": {"recent_warnings": [], "warning_categories": {}}, "screenshot_analysis": {}}
        mock_tests.return_value = {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False, "success": True}
        res = run_loop(dry_run=True, screenshot_category="champion_action")
        mock_diag.assert_called_once_with(category=None, screenshot_category="champion_action", error_category=None, crash_category=None)
        mock_tests.assert_called_once()

    def test_update_memory_state_error_and_crash_baseline(self):
        diag_mock = {
            "error_analysis": {
                "recent_errors": ["ERROR [LCU_TELEMETRY] Failed"],
                "error_categories": {"lcu_telemetry": 1},
                "recent_warnings": [],
                "warning_categories": {},
            },
            "crash_analysis": {
                "total_crash_sessions": 1,
                "total_actual_crashes": 2,
                "crash_categories": {"access_violation": 2},
            },
        }
        res = update_memory_state(
            metrics={"total_py_files": 10, "total_py_lines": 500, "breakdown": {}, "test_to_code_ratio": 0.5},
            test_results={"passed": 5, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False},
            dry_run=True,
            diagnostics_results=diag_mock,
        )
        eb = res["new_state"].get("error_baseline", {})
        self.assertEqual(eb.get("status"), "ERROR")
        self.assertEqual(eb.get("total_errors"), 1)
        self.assertEqual(eb.get("categories"), {"lcu_telemetry": 1})

        cb = res["new_state"].get("crash_baseline", {})
        self.assertEqual(cb.get("status"), "CRITICAL")
        self.assertEqual(cb.get("recent_crashes_count"), 1)
        self.assertEqual(cb.get("total_actual_crashes"), 2)
        self.assertEqual(cb.get("categories"), {"access_violation": 2})

    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    def test_run_loop_with_error_category(self, mock_tests, mock_diag):
        mock_diag.return_value = {"healthy": True, "error_analysis": {"recent_warnings": [], "warning_categories": {}, "recent_errors": []}, "screenshot_analysis": {}}
        mock_tests.return_value = {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False, "success": True}
        res = run_loop(dry_run=True, error_category="lcu_telemetry")
        mock_diag.assert_called_once_with(category=None, screenshot_category=None, error_category="lcu_telemetry", crash_category=None)
        mock_tests.assert_called_once()

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_error_category(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 284,
            "diagnostics": {
                "healthy": True,
                "error_analysis": {"filtered_error_category": "lcu_telemetry", "filtered_errors": ["ERROR [LCU_TELEMETRY] Failed"]},
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "entropy": {"status": "PASS", "avg_entropy": 50.0},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", ["autonomous_improvement_runner", "--error-category", "lcu_telemetry", "--dry-run"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_run_loop.assert_called_once()
            self.assertEqual(mock_run_loop.call_args[1].get("error_category"), "lcu_telemetry")


    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    def test_run_loop_with_crash_category(self, mock_tests, mock_diag):
        mock_diag.return_value = {"healthy": True, "error_analysis": {"recent_warnings": [], "warning_categories": {}, "recent_errors": []}, "crash_analysis": {}, "screenshot_analysis": {}}
        mock_tests.return_value = {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False, "success": True}
        res = run_loop(dry_run=True, crash_category="access_violation")
        mock_diag.assert_called_once_with(category=None, screenshot_category=None, error_category=None, crash_category="access_violation")
        mock_tests.assert_called_once()

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_crash_category(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 285,
            "diagnostics": {
                "healthy": True,
                "error_analysis": {},
                "crash_analysis": {"filtered_crash_category": "access_violation", "filtered_crashes": [{"session": "s1", "category": "access_violation", "summary": "Fatal exception"}]},
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "entropy": {"status": "PASS", "avg_entropy": 50.0},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", ["autonomous_improvement_runner", "--crash-category", "access_violation", "--dry-run"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_run_loop.assert_called_once()
            self.assertEqual(mock_run_loop.call_args[1].get("crash_category"), "access_violation")

    def test_update_memory_state_session_baseline(self):
        diag_mock = {
            "sessions_analysis": {
                "total_accounts": 4,
                "healthy_accounts": 3,
                "corrupted_accounts": 1,
                "stale_accounts": 1,
            }
        }
        res = update_memory_state(
            metrics={"total_py_files": 10, "total_py_lines": 500, "breakdown": {}, "test_to_code_ratio": 0.5},
            test_results={"passed": 5, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False},
            dry_run=True,
            diagnostics_results=diag_mock,
        )
        sb = res["new_state"].get("session_baseline", {})
        self.assertEqual(sb.get("status"), "CORRUPTED")
        self.assertEqual(sb.get("total_accounts"), 4)
        self.assertEqual(sb.get("healthy_accounts"), 3)
        self.assertEqual(sb.get("corrupted_accounts"), 1)
        self.assertEqual(sb.get("stale_accounts"), 1)

    @patch("tools.leagueloop_diagnostics.run_diagnostics")
    def test_run_diagnostics_check_with_session_filters(self, mock_diag):
        mock_diag.return_value = {"healthy": True}
        run_diagnostics_check(session_status="healthy", session_account="alpha")
        mock_diag.assert_called_once_with(filter_session_status="healthy", filter_session_account="alpha")

    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    def test_run_loop_with_session_filters(self, mock_tests, mock_diag):
        mock_diag.return_value = {"healthy": True, "error_analysis": {}, "crash_analysis": {}, "screenshot_analysis": {}, "sessions_analysis": {}}
        mock_tests.return_value = {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False, "success": True}
        res = run_loop(dry_run=True, session_status="healthy", session_account="pro_acc")
        mock_diag.assert_called_once_with(
            category=None,
            screenshot_category=None,
            error_category=None,
            crash_category=None,
            session_status="healthy",
            session_account="pro_acc",
        )
        mock_tests.assert_called_once()

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_session_filters(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 286,
            "diagnostics": {
                "healthy": True,
                "error_analysis": {},
                "crash_analysis": {},
                "sessions_analysis": {
                    "filtered_status": "healthy",
                    "filtered_account": "pro_acc",
                    "filtered_accounts": [{"account_id": "pro_acc", "slot_name": "slot_1"}],
                },
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "entropy": {"status": "PASS", "avg_entropy": 50.0},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", ["autonomous_improvement_runner", "--session-status", "healthy", "--session-account", "pro_acc", "--dry-run"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_run_loop.assert_called_once()
            self.assertEqual(mock_run_loop.call_args[1].get("session_status"), "healthy")
            self.assertEqual(mock_run_loop.call_args[1].get("session_account"), "pro_acc")


    def test_update_memory_state_stability_baseline(self):
        diag_mock = {
            "session_analysis": {
                "stability": {
                    "rating": "EXCELLENT",
                    "connection_drops_count": 0,
                    "recovered_drops_count": 0,
                    "throttle_events_count": 0,
                    "is_connected": True,
                    "latency_stats": {"avg_ms": 42.5},
                }
            }
        }
        res = update_memory_state(
            metrics={"total_py_files": 10, "total_py_lines": 500, "breakdown": {}, "test_to_code_ratio": 0.5},
            test_results={"passed": 5, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False},
            dry_run=True,
            diagnostics_results=diag_mock,
        )
        sb = res["new_state"].get("stability_baseline", {})
        self.assertEqual(sb.get("status"), "OPTIMAL")
        self.assertEqual(sb.get("rating"), "EXCELLENT")
        self.assertEqual(sb.get("connection_drops"), 0)
        self.assertEqual(sb.get("throttle_events"), 0)
        self.assertTrue(sb.get("is_connected"))
        self.assertEqual(sb.get("latency_avg_ms"), 42.5)

    @patch("tools.leagueloop_diagnostics.run_diagnostics")
    def test_run_diagnostics_check_with_session_log_filters(self, mock_diag):
        mock_diag.return_value = {"healthy": True}
        run_diagnostics_check(session_log_level="WARNING", session_log_tag="LCU_WS")
        mock_diag.assert_called_once_with(filter_session_log_level="WARNING", filter_session_log_tag="LCU_WS")

    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    def test_run_loop_with_session_log_filters(self, mock_tests, mock_diag):
        mock_diag.return_value = {"healthy": True, "error_analysis": {}, "crash_analysis": {}, "screenshot_analysis": {}, "sessions_analysis": {}, "session_analysis": {"stability": {}}}
        mock_tests.return_value = {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False, "success": True}
        res = run_loop(dry_run=True, session_log_level="WARNING", session_log_tag="LCU_WS")
        mock_diag.assert_called_once_with(
            category=None,
            screenshot_category=None,
            error_category=None,
            crash_category=None,
            session_log_level="WARNING",
            session_log_tag="LCU_WS",
        )
        mock_tests.assert_called_once()

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_session_log_filters(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 288,
            "diagnostics": {
                "healthy": True,
                "error_analysis": {},
                "crash_analysis": {},
                "sessions_analysis": {},
                "session_analysis": {
                    "filtered_level": "WARNING",
                    "filtered_tag": "LCU_WS",
                    "filtered_entries": [{"level": "WARNING", "tag": "LCU_WS", "msg": "Dropped"}],
                    "stability": {"rating": "GOOD", "connection_drops_count": 0, "throttle_events_count": 0},
                },
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "entropy": {"status": "PASS", "avg_entropy": 50.0},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", ["autonomous_improvement_runner", "--session-log-level", "WARNING", "--session-log-tag", "LCU_WS", "--dry-run"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_run_loop.assert_called_once()
            self.assertEqual(mock_run_loop.call_args[1].get("session_log_level"), "WARNING")
            self.assertEqual(mock_run_loop.call_args[1].get("session_log_tag"), "LCU_WS")

    def test_update_memory_state_debug_baseline(self):
        diag_mock = {
            "debug_analysis": {
                "total_lines_inspected": 150,
                "diagnostic_tags_count": 3,
                "level_counts": {"INFO": 100, "ACTION": 40, "WARNING": 10},
            }
        }
        res = update_memory_state(
            metrics={"total_py_files": 10, "total_py_lines": 500, "breakdown": {}, "test_to_code_ratio": 0.5},
            test_results={"passed": 5, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False},
            dry_run=True,
            diagnostics_results=diag_mock,
        )
        db = res["new_state"].get("debug_baseline", {})
        self.assertEqual(db.get("status"), "WARN")
        self.assertEqual(db.get("total_lines_inspected"), 150)
        self.assertEqual(db.get("diagnostic_tags_count"), 3)
        self.assertEqual(db.get("level_counts", {}).get("ACTION"), 40)

    @patch("tools.leagueloop_diagnostics.run_diagnostics")
    def test_run_diagnostics_check_with_debug_log_filters(self, mock_diag):
        mock_diag.return_value = {"healthy": True}
        run_diagnostics_check(debug_level="ACTION", debug_tag="Automation")
        mock_diag.assert_called_once_with(filter_debug_level="ACTION", filter_debug_tag="Automation")

    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    def test_run_loop_with_debug_log_filters(self, mock_tests, mock_diag):
        mock_diag.return_value = {"healthy": True, "error_analysis": {}, "crash_analysis": {}, "screenshot_analysis": {}, "sessions_analysis": {}, "session_analysis": {"stability": {}}, "debug_analysis": {}}
        mock_tests.return_value = {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False, "success": True}
        res = run_loop(dry_run=True, debug_level="ACTION", debug_tag="Automation")
        mock_diag.assert_called_once_with(
            category=None,
            screenshot_category=None,
            error_category=None,
            crash_category=None,
            debug_level="ACTION",
            debug_tag="Automation",
        )
        mock_tests.assert_called_once()

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_debug_log_filters(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 289,
            "diagnostics": {
                "healthy": True,
                "error_analysis": {},
                "crash_analysis": {},
                "sessions_analysis": {},
                "session_analysis": {"stability": {"rating": "GOOD"}},
                "debug_analysis": {
                    "filtered_level": "ACTION",
                    "filtered_tag": "Automation",
                    "filtered_entries": ["2026-10-14 10:00:00 ACTION [Automation] Draft lock"],
                },
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "entropy": {"status": "PASS", "avg_entropy": 50.0},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", ["autonomous_improvement_runner", "--debug-level", "ACTION", "--debug-tag", "Automation", "--dry-run"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_run_loop.assert_called_once()
            self.assertEqual(mock_run_loop.call_args[1].get("debug_level"), "ACTION")
            self.assertEqual(mock_run_loop.call_args[1].get("debug_tag"), "Automation")

    @patch("tools.leagueloop_diagnostics.run_diagnostics")
    def test_run_diagnostics_check_with_storage_thresholds(self, mock_diag):
        mock_diag.return_value = {"healthy": True}
        run_diagnostics_check(max_logs_mb=50.0, max_screenshots_mb=75.0, strict_storage=True, include_rotated=True)
        mock_diag.assert_called_once_with(
            max_logs_mb=50.0,
            max_screenshots_mb=75.0,
            strict_storage=True,
            include_rotated=True,
        )

    def test_update_memory_state_pruning_baseline_and_thresholds(self):
        diag_mock = {
            "debug_analysis": {"total_lines_inspected": 10, "diagnostic_tags_count": 0, "level_counts": {}},
            "storage_analysis": {
                "status": "OPTIMAL",
                "total_mb": 45.0,
                "logs": {"total_mb": 15.0},
                "screenshots": {"total_mb": 30.0},
                "warnings": [],
                "thresholds": {"max_logs_mb": 50.0, "max_screenshots_mb": 75.0},
            },
        }
        prune_mock = {
            "total_freed_mb": 12.5,
            "logs_pruned": {"count": 3, "mb": 5.0},
            "screenshots_pruned": {"count": 10, "mb": 7.5},
        }
        res = update_memory_state(
            metrics={"total_py_files": 10, "total_py_lines": 500, "breakdown": {}, "test_to_code_ratio": 0.5},
            test_results={"passed": 5, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False},
            dry_run=True,
            diagnostics_results=diag_mock,
            storage_results=diag_mock["storage_analysis"],
            prune_results=prune_mock,
        )
        sb = res["new_state"].get("storage_baseline", {})
        self.assertEqual(sb.get("thresholds", {}).get("max_logs_mb"), 50.0)
        self.assertEqual(sb.get("thresholds", {}).get("max_screenshots_mb"), 75.0)

        pb = res["new_state"].get("pruning_baseline", {})
        self.assertEqual(pb.get("status"), "PRUNED")
        self.assertEqual(pb.get("last_freed_mb"), 12.5)
        self.assertEqual(pb.get("logs_pruned_count"), 3)
        self.assertEqual(pb.get("screenshots_pruned_count"), 10)

    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    @patch("tools.leagueloop_diagnostics.prune_storage")
    def test_run_loop_with_storage_governance(self, mock_prune, mock_tests, mock_diag):
        mock_prune.return_value = {
            "total_freed_mb": 5.0,
            "logs_pruned": {"count": 1, "mb": 2.0},
            "screenshots_pruned": {"count": 5, "mb": 3.0},
        }
        mock_diag.return_value = {
            "healthy": True,
            "error_analysis": {},
            "crash_analysis": {},
            "screenshot_analysis": {},
            "sessions_analysis": {},
            "session_analysis": {"stability": {}},
            "debug_analysis": {},
            "storage_analysis": {"status": "OPTIMAL", "total_mb": 40.0, "logs": {}, "screenshots": {}},
        }
        mock_tests.return_value = {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False, "success": True}
        res = run_loop(
            dry_run=True,
            prune_storage_flag=True,
            keep_rotated_logs=True,
            max_logs_mb=60.0,
            max_screenshots_mb=80.0,
            strict_storage=True,
            include_rotated=True,
        )
        mock_prune.assert_called_once()
        self.assertFalse(mock_prune.call_args[1].get("prune_rotated_logs"))
        mock_diag.assert_called_once_with(
            category=None,
            screenshot_category=None,
            error_category=None,
            crash_category=None,
            max_logs_mb=60.0,
            max_screenshots_mb=80.0,
            strict_storage=True,
            include_rotated=True,
        )
        self.assertIsNotNone(res.get("prune_results"))

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_storage_governance_flags(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 291,
            "diagnostics": {
                "healthy": True,
                "error_analysis": {},
                "crash_analysis": {},
                "sessions_analysis": {},
                "session_analysis": {"stability": {"rating": "GOOD"}},
                "debug_analysis": {},
                "storage_analysis": {"status": "OPTIMAL", "total_mb": 40.0},
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "entropy": {"status": "PASS", "avg_entropy": 50.0},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--max-logs-mb", "80.0",
            "--max-screenshots-mb", "120.0",
            "--strict-storage",
            "--include-rotated",
            "--keep-rotated-logs",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_run_loop.assert_called_once()
            kwargs = mock_run_loop.call_args[1]
            self.assertEqual(kwargs.get("max_logs_mb"), 80.0)
            self.assertEqual(kwargs.get("max_screenshots_mb"), 120.0)
            self.assertTrue(kwargs.get("strict_storage"))
            self.assertTrue(kwargs.get("include_rotated"))
            self.assertTrue(kwargs.get("keep_rotated_logs"))

    def test_update_memory_state_records_build_and_accounts_baselines(self):
        build_health_mock = {
            "status": "HEALTHY",
            "version": "2-10-303-2009",
            "version_aligned": True,
            "files_ok": True,
            "test_environment_ok": True,
            "duration_ms": 1.25,
        }
        accounts_preflight_mock = {
            "status": "HEALTHY",
            "accounts_count": 4,
            "usable_sessions_count": 4,
            "expired_sessions_count": 0,
            "missing_sessions_count": 0,
            "problems_count": 0,
            "vault_wired": True,
            "switcher_wired": True,
            "riot_client_running": True,
            "signed_in": True,
            "api_reachable": True,
            "current_user": "themalcolm3",
        }
        res = update_memory_state(
            metrics={"total_py_files": 10, "total_py_lines": 500, "breakdown": {}, "test_to_code_ratio": 0.5},
            test_results={"passed": 5, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "run_all": False},
            dry_run=True,
            build_health_results=build_health_mock,
            accounts_preflight_results=accounts_preflight_mock,
        )
        new_state = res["new_state"]
        self.assertIn("build_baseline", new_state)
        self.assertEqual(new_state["build_baseline"]["status"], "HEALTHY")
        self.assertEqual(new_state["build_baseline"]["version"], "2-10-303-2009")
        self.assertTrue(new_state["build_baseline"]["version_aligned"])
        self.assertTrue(new_state["build_baseline"]["files_ok"])
        self.assertEqual(new_state["build_baseline"]["duration_ms"], 1.25)

        self.assertIn("accounts_preflight_baseline", new_state)
        self.assertEqual(new_state["accounts_preflight_baseline"]["status"], "HEALTHY")
        self.assertEqual(new_state["accounts_preflight_baseline"]["accounts_count"], 4)
        self.assertEqual(new_state["accounts_preflight_baseline"]["usable_sessions_count"], 4)
        self.assertEqual(new_state["accounts_preflight_baseline"]["problems_count"], 0)
        self.assertTrue(new_state["accounts_preflight_baseline"]["vault_wired"])
        self.assertEqual(new_state["accounts_preflight_baseline"]["current_user"], "themalcolm3")

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_build_and_preflight_success(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 292,
            "diagnostics": {"healthy": True, "error_analysis": {}, "storage_analysis": {"status": "OPTIMAL"}},
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 4, "usable_sessions_count": 4, "problems_count": 0},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-build",
            "--strict-preflight",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_run_loop.assert_called_once()
            kwargs = mock_run_loop.call_args[1]
            self.assertTrue(kwargs.get("strict_build"))
            self.assertTrue(kwargs.get("strict_preflight"))

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_build_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 292,
            "diagnostics": {"healthy": True, "error_analysis": {}},
            "version_alignment": {"aligned": False, "message": "mismatch"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-build",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_preflight_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 292,
            "diagnostics": {"healthy": True, "error_analysis": {}},
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "WARN", "accounts_count": 4, "usable_sessions_count": 2, "problems_count": 2},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-accounts",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_entropy_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 293,
            "diagnostics": {"healthy": True, "error_analysis": {}},
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "FAIL", "avg_entropy": 80.0, "bare_excepts_total": 1, "syntax_errors": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-entropy",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_max_entropy_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 293,
            "diagnostics": {"healthy": True, "error_analysis": {}},
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "WARN", "avg_entropy": 75.5, "bare_excepts_total": 0, "syntax_errors": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--max-entropy", "65.0",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_silent_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 293,
            "diagnostics": {"healthy": True, "error_analysis": {}},
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "PASS", "avg_entropy": 25.0, "bare_excepts_total": 0, "syntax_errors": 0},
            "silent_excepts": {"status": "WARN", "silent_handlers_count": 2, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-silent",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)


    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_warnings_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 294,
            "diagnostics": {"healthy": True, "error_analysis": {"recent_warnings": ["w1", "w2"], "status": "WARN"}},
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "PASS", "avg_entropy": 25.0, "bare_excepts_total": 0, "syntax_errors": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-warnings",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_max_warnings_threshold(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 294,
            "diagnostics": {"healthy": True, "error_analysis": {"recent_warnings": ["w1", "w2", "w3"], "status": "WARN"}},
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "PASS", "avg_entropy": 25.0, "bare_excepts_total": 0, "syntax_errors": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        # Exceeded: 3 warnings > limit of 2 -> exit 1
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--max-warnings", "2",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

        # Within limit: 3 warnings <= limit of 5 -> exit 0
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--max-warnings", "5",
            "--dry-run"
        ]):
            try:
                main()
            except SystemExit as e:
                self.assertEqual(e.code, 0)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_stability_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 294,
            "diagnostics": {
                "healthy": True,
                "error_analysis": {},
                "session_analysis": {
                    "stability": {"rating": "DEGRADED", "connection_drops_count": 2, "throttle_events_count": 1}
                }
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "PASS", "avg_entropy": 25.0, "bare_excepts_total": 0, "syntax_errors": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-stability",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_screenshots_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 294,
            "diagnostics": {
                "healthy": True,
                "error_analysis": {},
                "screenshot_analysis": {"all_intact": False, "corrupted_count": 1, "stale_count": 0}
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "PASS", "avg_entropy": 25.0, "bare_excepts_total": 0, "syntax_errors": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-screenshots",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    def test_update_memory_state_governance_thresholds(self):
        from tools.autonomous_improvement_runner import update_memory_state
        metrics = {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5}
        test_results = {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True}
        res = update_memory_state(
            metrics,
            test_results,
            dry_run=True,
            max_warnings_threshold=25,
            strict_warnings=True,
            strict_stability=True,
            strict_screenshots=True,
            max_errors_threshold=5,
            strict_errors=True,
            max_crashes_threshold=0,
            strict_crashes=True,
            strict_sessions=True,
            strict_debug=True,
        )
        new_state = res["new_state"]
        self.assertEqual(new_state["warning_baseline"]["thresholds"]["max_warnings"], 25)
        self.assertTrue(new_state["warning_baseline"]["thresholds"]["strict"])
        self.assertTrue(new_state["stability_baseline"]["thresholds"]["strict"])
        self.assertEqual(new_state["stability_baseline"]["thresholds"]["allowed_ratings"], ["EXCELLENT"])
        self.assertTrue(new_state["screenshot_baseline"]["thresholds"]["strict"])
        self.assertEqual(new_state["screenshot_baseline"]["thresholds"]["max_corrupted"], 0)
        self.assertEqual(new_state["error_baseline"]["thresholds"]["max_errors"], 5)
        self.assertTrue(new_state["error_baseline"]["thresholds"]["strict"])
        self.assertEqual(new_state["crash_baseline"]["thresholds"]["max_crashes"], 0)
        self.assertTrue(new_state["crash_baseline"]["thresholds"]["strict"])
        self.assertTrue(new_state["session_baseline"]["thresholds"]["strict"])
        self.assertEqual(new_state["session_baseline"]["thresholds"]["max_stale"], 0)
        self.assertTrue(new_state["debug_baseline"]["thresholds"]["strict"])
        self.assertEqual(new_state["debug_baseline"]["thresholds"]["max_errors"], 0)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_errors_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 295,
            "diagnostics": {
                "healthy": True,
                "error_analysis": {"recent_errors": ["Error occurred"], "status": "ERROR"},
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "PASS", "avg_entropy": 25.0, "bare_excepts_total": 0, "syntax_errors": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-errors",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_max_errors_threshold(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 295,
            "diagnostics": {
                "healthy": True,
                "error_analysis": {"recent_errors": ["e1", "e2", "e3"]},
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "PASS", "avg_entropy": 25.0, "bare_excepts_total": 0, "syntax_errors": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        # Exceeded: 3 errors > limit 2 -> exit 1
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--max-errors", "2",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

        # Within limit: 3 errors <= limit 4 -> exit 0
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--max-errors", "4",
            "--dry-run"
        ]):
            try:
                main()
            except SystemExit as e:
                self.assertEqual(e.code, 0)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_crashes_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 295,
            "diagnostics": {
                "healthy": True,
                "crash_analysis": {"total_crash_sessions": 1, "status": "CRITICAL"},
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "PASS", "avg_entropy": 25.0, "bare_excepts_total": 0, "syntax_errors": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-crashes",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_sessions_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 295,
            "diagnostics": {
                "healthy": True,
                "sessions_analysis": {"corrupted_accounts": 1, "stale_accounts": 0, "status": "CORRUPTED"},
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "PASS", "avg_entropy": 25.0, "bare_excepts_total": 0, "syntax_errors": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-sessions",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch("tools.autonomous_improvement_runner.run_loop")
    def test_main_cli_strict_debug_failure(self, mock_run_loop):
        from tools.autonomous_improvement_runner import main
        mock_run_loop.return_value = {
            "loop_number": 295,
            "diagnostics": {
                "healthy": True,
                "debug_analysis": {"level_counts": {"ERROR": 1, "CRITICAL": 0}, "status": "ERROR"},
            },
            "version_alignment": {"aligned": True, "message": "aligned"},
            "build_assets": {"ready": True, "message": "ready"},
            "build_health": {"status": "HEALTHY", "version": "1.0", "duration_ms": 1.0},
            "accounts_preflight": {"status": "HEALTHY", "accounts_count": 1, "usable_sessions_count": 1, "problems_count": 0},
            "entropy": {"status": "PASS", "avg_entropy": 25.0, "bare_excepts_total": 0, "syntax_errors": 0},
            "silent_excepts": {"status": "PASS", "silent_handlers_count": 0, "files_audited": 10},
            "tests": {"passed": 10, "failed": 0, "skipped": 0, "warnings": 0, "errors": 0, "duration_seconds": 1.0, "success": True},
            "metrics": {"total_py_files": 10, "total_py_lines": 500, "test_to_code_ratio": 0.5},
            "memory": {"persisted": False, "episodic_entry": {"outcome": "Success"}},
        }
        with patch("sys.argv", [
            "autonomous_improvement_runner",
            "--strict-debug",
            "--dry-run"
        ]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
