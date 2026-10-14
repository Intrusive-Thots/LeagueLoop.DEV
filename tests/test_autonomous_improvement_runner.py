import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.autonomous_improvement_runner import (
    measure_codebase_metrics,
    run_diagnostics_check,
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

    def test_update_memory_state_dry_run(self):
        metrics = {"total_py_files": 150, "total_py_lines": 45000}
        tests = {"passed": 787, "failed": 0, "duration_seconds": 17.5}
        result = update_memory_state(metrics, tests, dry_run=True)

        self.assertFalse(result["persisted"])
        self.assertIn("new_state", result)
        self.assertEqual(result["new_state"]["test_baseline"]["passed"], 787)
        self.assertEqual(result["new_state"]["index_baseline"]["total_files"], 150)

    @patch("tools.autonomous_improvement_runner.run_diagnostics_check")
    @patch("tools.autonomous_improvement_runner.run_tests_check")
    @patch("tools.autonomous_improvement_runner.sync_mempalace")
    def test_run_loop_dry_run(self, mock_mempalace, mock_tests, mock_diag):
        mock_diag.return_value = {"healthy": True}
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
        self.assertTrue(res["tests"]["success"])
        self.assertFalse(res["memory"]["persisted"])


if __name__ == "__main__":
    unittest.main()
