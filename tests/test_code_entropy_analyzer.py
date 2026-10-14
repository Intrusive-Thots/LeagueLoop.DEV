import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.code_entropy_analyzer import (
    analyze_python_file,
    analyze_directory,
    run_entropy_summary,
)


class TestCodeEntropyAnalyzer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_analyze_clean_file(self):
        file_path = self.base / "clean.py"
        file_path.write_text(
            "def add(a, b):\n"
            "    return a + b\n",
            encoding="utf-8"
        )
        res = analyze_python_file(str(file_path))
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["functions"], 1)
        self.assertEqual(len(res["bare_excepts"]), 0)

    def test_analyze_bare_except(self):
        file_path = self.base / "bad_except.py"
        file_path.write_text(
            "try:\n"
            "    x = 1 / 0\n"
            "except:\n"
            "    pass\n",
            encoding="utf-8"
        )
        res = analyze_python_file(str(file_path))
        self.assertIn(3, res["bare_excepts"])
        self.assertGreater(res["entropy_score"], 0)

    def test_run_entropy_summary(self):
        file_path = self.base / "sample.py"
        file_path.write_text(
            "class MyClass:\n"
            "    def method(self, x):\n"
            "        if x > 0:\n"
            "            return True\n"
            "        return False\n",
            encoding="utf-8"
        )
        summary = run_entropy_summary(str(self.base))
        self.assertEqual(summary["total_files"], 1)
        self.assertEqual(summary["bare_excepts_total"], 0)
        self.assertEqual(summary["syntax_errors"], 0)
        self.assertEqual(summary["status"], "PASS")

    def test_main_cli_arguments(self):
        from tools.code_entropy_analyzer import main
        file_path = self.base / "cli_sample.py"
        file_path.write_text("def ping(): return True\n", encoding="utf-8")

        # Test positional argument with --json
        with patch("sys.stdout") as mock_stdout:
            main([str(file_path), "--json"])

        # Test --target argument
        with patch("sys.stdout") as mock_stdout:
            main(["--target", str(file_path), "--json"])


if __name__ == "__main__":
    unittest.main()
