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

    def test_get_git_modified_files_returns_set(self):
        res = get_git_modified_files()
        self.assertIsInstance(res, set)


if __name__ == "__main__":
    unittest.main()
