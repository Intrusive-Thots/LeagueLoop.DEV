import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.autonomous_improvement_runner import (
    measure_codebase_metrics,
    run_diagnostics_check,
    run_entropy_check,
    update_memory_state,
    run_loop,
)


class TestAutonomousImprovementRunner(unittest.TestCase):
    def test_measure_codebase_metrics(self):
        metrics = measure_codebase_metrics()
        self.assertIn("total_py_files", metrics)
        self.assertIn("total_py_lines", metrics)
        self.assertGreater(metrics["total_py_files"], 0)
        self.assertGreater(metrics["total_py_lines"], 0)

    @patch("tools.leagueloop_diagnostics.run_diagnostics")
    def test_run_diagnostics_check(self, mock_diag):
        mock_diag.return_value = {"healthy": True, "error_analysis": {}}
        diag = run_diagnostics_check()
        self.assertTrue(diag["healthy"])

    @patch("tools.code_entropy_analyzer.run_entropy_summary")
    def test_run_entropy_check(self, mock_entropy):
        mock_entropy.return_value = {"status": "PASS", "avg_entropy": 12.5, "bare_excepts_total": 0}
        entropy = run_entropy_check()
        self.assertEqual(entropy["status"], "PASS")

    def test_update_memory_state_dry_run(self):
        metrics = {"total_py_files": 150, "total_py_lines": 45000}
        tests = {"passed": 787, "failed": 0, "duration_seconds": 17.5}
        result = update_memory_state(
            metrics,
            tests,
            dry_run=True,
            semantic_learnings=[{"concept": "Test Concept", "description": "Desc"}],
            procedural_methods=[{"method": "Test Method", "procedure": ["Step 1"]}],
        )

        self.assertFalse(result["persisted"])
        self.assertIn("new_state", result)
        self.assertEqual(result["new_state"]["test_baseline"]["passed"], 787)
        self.assertEqual(result["new_state"]["index_baseline"]["total_files"], 150)
        self.assertEqual(len(result["semantic_learnings"]), 1)
        self.assertEqual(len(result["procedural_methods"]), 1)

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


if __name__ == "__main__":
    unittest.main()
