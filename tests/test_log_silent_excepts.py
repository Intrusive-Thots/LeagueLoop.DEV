import json
import tempfile
import unittest
from pathlib import Path

from tools.log_silent_excepts import scan_silent_handlers, sites, main


class TestLogSilentExcepts(unittest.TestCase):
    def test_scan_clean_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "clean.py"
            f.write_text("def test():\n    try:\n        x = 1\n    except KeyError:\n        pass\n", encoding="utf-8")
            res = scan_silent_handlers(paths=[tmpdir])
            self.assertEqual(res["status"], "PASS")
            self.assertEqual(res["silent_handlers_count"], 0)
            self.assertEqual(res["files_audited"], 1)

    def test_scan_broad_exception_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "swallow.py"
            f.write_text("def test():\n    try:\n        x = 1\n    except Exception:\n        pass\n", encoding="utf-8")
            res = scan_silent_handlers(paths=[tmpdir])
            self.assertEqual(res["status"], "FAIL")
            self.assertEqual(res["silent_handlers_count"], 1)
            self.assertEqual(len(res["offending_files"]), 1)
            self.assertIn("1 silent handler(s)", res["message"])

    def test_scan_bare_except_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "bare.py"
            f.write_text("def test():\n    try:\n        x = 1\n    except:\n        pass\n", encoding="utf-8")
            res = scan_silent_handlers(paths=[tmpdir])
            self.assertEqual(res["status"], "FAIL")
            self.assertEqual(res["silent_handlers_count"], 1)

    def test_scan_nonexistent_path(self):
        res = scan_silent_handlers(paths=["/nonexistent/path/xyz"])
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["files_audited"], 0)

    def test_scan_single_file_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "sample.py"
            f.write_text("def test():\n    return 42\n", encoding="utf-8")
            res = scan_silent_handlers(paths=[f])
            self.assertEqual(res["status"], "PASS")
            self.assertEqual(res["files_audited"], 1)

    def test_main_cli_json(self):
        from io import StringIO
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "clean.py"
            f.write_text("def test():\n    return 10\n", encoding="utf-8")
            buf = StringIO()
            with patch("sys.stdout", buf):
                code = main(["--json", str(tmpdir)])
            self.assertEqual(code, 0)
            data = json.loads(buf.getvalue().strip())
            self.assertEqual(data["status"], "PASS")
            self.assertEqual(data["silent_handlers_count"], 0)

    def test_main_cli_human(self):
        from io import StringIO
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "clean.py"
            f.write_text("def test():\n    return 10\n", encoding="utf-8")
            buf = StringIO()
            with patch("sys.stdout", buf):
                code = main([str(tmpdir)])
            self.assertEqual(code, 0)
            self.assertIn("0 silent handler(s)", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
