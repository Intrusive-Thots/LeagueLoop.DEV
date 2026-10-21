import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.fast_test_runner import (
    ASTTestDependencyGraph,
    map_source_to_tests,
    get_git_modified_files,
    PROJECT_ROOT,
    TESTS_DIR,
)


class TestFastTestRunner(unittest.TestCase):
    def setUp(self):
        self.graph = ASTTestDependencyGraph(TESTS_DIR)

    def test_ast_dependency_graph_indexing(self):
        self.assertGreater(len(self.graph.module_to_tests), 0)
        # Should contain standard modules indexed from tests
        self.assertTrue(any("events" in k for k in self.graph.module_to_tests.keys()))

    def test_find_tests_for_source_core_events(self):
        matches = self.graph.find_tests_for_source("src/core/events.py")
        self.assertIsInstance(matches, set)
        # Should match at least one test suite
        self.assertGreater(len(matches), 0)

    def test_map_source_to_tests_direct_test_file(self):
        targets = {"tests/test_fast_test_runner.py"}
        mapped = map_source_to_tests(targets, self.graph)
        self.assertIn(str((TESTS_DIR / "test_fast_test_runner.py").resolve()), mapped)

    def test_map_source_to_tests_tools_module(self):
        targets = {"tools/leagueloop_diagnostics.py"}
        mapped = map_source_to_tests(targets, self.graph)
        self.assertTrue(any("test_leagueloop_diagnostics.py" in t for t in mapped))

    def test_map_source_to_tests_specialized_services(self):
        targets = {"src/services/loot_service.py"}
        mapped = map_source_to_tests(targets, self.graph)
        self.assertTrue(any("test_loot_service.py" in t for t in mapped))

    def test_map_source_to_tests_pytest_node_id(self):
        target = "tests/test_fast_test_runner.py::TestFastTestRunner::test_ast_dependency_graph_indexing"
        mapped = map_source_to_tests({target}, self.graph)
        self.assertEqual(len(mapped), 1)
        expected_prefix = str((TESTS_DIR / "test_fast_test_runner.py").resolve())
        self.assertTrue(mapped[0].startswith(expected_prefix))
        self.assertTrue(mapped[0].endswith("::TestFastTestRunner::test_ast_dependency_graph_indexing"))

    @patch("tools.fast_test_runner.run_tests")
    def test_main_argv_node_id_and_extra_flags(self, mock_run):
        from tools.fast_test_runner import main as runner_main
        mock_run.return_value = 0
        with self.assertRaises(SystemExit) as cm:
            runner_main(["tests/test_fast_test_runner.py::TestFastTestRunner", "-k", "test_ast", "-x"])
        self.assertEqual(cm.exception.code, 0)
        self.assertTrue(mock_run.called)
        call_targets, call_extra = mock_run.call_args[0]
        self.assertTrue(any("::TestFastTestRunner" in t for t in call_targets))
        self.assertIn("-k", call_extra)
        self.assertIn("test_ast", call_extra)
        self.assertIn("-x", call_extra)

    @patch("tools.fast_test_runner.run_tests")
    def test_main_argv_all_tests_with_flags(self, mock_run):
        from tools.fast_test_runner import main as runner_main
        mock_run.return_value = 0
        with self.assertRaises(SystemExit) as cm:
            runner_main(["--all", "-v"])
        self.assertEqual(cm.exception.code, 0)
        mock_run.assert_called_once_with([], ["-v"])

    @patch("tools.fast_test_runner.run_tests")
    def test_main_argv_default_empty(self, mock_run):
        from tools.fast_test_runner import main as runner_main
        mock_run.return_value = 0
        with self.assertRaises(SystemExit) as cm:
            runner_main([])
        self.assertEqual(cm.exception.code, 0)
        self.assertTrue(mock_run.called)

    @patch("tools.fast_test_runner.run_tests")
    def test_main_argv_staged(self, mock_run):
        from tools.fast_test_runner import main as runner_main
        mock_run.return_value = 0
        with self.assertRaises(SystemExit) as cm:
            runner_main(["--staged"])
        self.assertEqual(cm.exception.code, 0)
        self.assertTrue(mock_run.called)

    def test_main_argv_summary(self):
        from tools.fast_test_runner import main as runner_main
        with patch("sys.stdout"):
            with self.assertRaises(SystemExit) as cm:
                runner_main(["--summary"])
            self.assertEqual(cm.exception.code, 0)

    def test_main_argv_graph(self):
        from tools.fast_test_runner import main as runner_main
        with patch("sys.stdout"):
            with self.assertRaises(SystemExit) as cm:
                runner_main(["--graph"])
            self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
