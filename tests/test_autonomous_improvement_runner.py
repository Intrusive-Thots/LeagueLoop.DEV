import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from tools.autonomous_improvement_runner import (
    measure_codebase_metrics,
    run_diagnostics_check,
    run_version_alignment_check,
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
            )


if __name__ == "__main__":
    unittest.main()
