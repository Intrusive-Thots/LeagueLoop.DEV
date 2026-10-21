import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.build_validator import (
    validate_version,
    validate_version_alignment,
    validate_files,
    validate_test_suite,
    verify_system_wide_health,
    get_build_validation_telemetry,
    run_full_validation_cycle,
    main,
)


class TestBuildValidatorComprehensive(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Setup standard directory structure
        self.src_core = self.root / "src" / "core"
        self.src_core.mkdir(parents=True, exist_ok=True)
        self.version_file = self.src_core / "version.py"
        self.version_file.write_text('__version__ = "2-10-289-1636"\n', encoding="utf-8")

        self.installer_file = self.root / "installer.iss"
        self.installer_file.write_text(
            '#define AppVersion "2-10-289-1636"\n'
            '#define VersionInfoVersion "2.10.289.1636"\n',
            encoding="utf-8"
        )

        self.spec_file = self.root / "LeagueLoop.spec"
        self.spec_file.write_text("# spec dummy\n", encoding="utf-8")

        self.tokens_file = self.root / "src" / "ui" / "theme" / "design_tokens.json"
        self.tokens_file.parent.mkdir(parents=True, exist_ok=True)
        self.tokens_file.write_text("{}", encoding="utf-8")

        self.icon_file = self.root / "assets" / "app.ico"
        self.icon_file.parent.mkdir(parents=True, exist_ok=True)
        self.icon_file.write_text("dummy icon", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_validate_version_success(self):
        ver = validate_version(self.root)
        self.assertEqual(ver, "2-10-289-1636")

    def test_validate_version_missing_file(self):
        self.version_file.unlink()
        with self.assertRaises(FileNotFoundError):
            validate_version(self.root)

    def test_validate_version_invalid_format(self):
        self.version_file.write_text('invalid_content = 123\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            validate_version(self.root)

    def test_validate_version_alignment_success(self):
        ok, msg = validate_version_alignment(self.root)
        self.assertTrue(ok)
        self.assertIn("aligned", msg)

    def test_validate_version_alignment_mismatch(self):
        self.installer_file.write_text(
            '#define AppVersion "2-10-288-0000"\n'
            '#define VersionInfoVersion "2.10.288.0000"\n',
            encoding="utf-8"
        )
        ok, msg = validate_version_alignment(self.root)
        self.assertFalse(ok)
        self.assertIn("does not match", msg)

    def test_validate_files_all_present(self):
        self.assertTrue(validate_files(self.root))

    def test_validate_files_missing(self):
        self.icon_file.unlink()
        self.assertFalse(validate_files(self.root))

    @patch("pytest.main", return_value=0)
    def test_validate_test_suite_success(self, mock_pytest):
        self.assertTrue(validate_test_suite(self.root))
        self.assertTrue(mock_pytest.called)

    @patch("pytest.main", return_value=1)
    def test_validate_test_suite_failure(self, mock_pytest):
        self.assertFalse(validate_test_suite(self.root))

    def test_verify_system_wide_health(self):
        health = verify_system_wide_health(self.root)
        self.assertEqual(health["status"], "HEALTHY")
        self.assertTrue(health["version_aligned"])
        self.assertTrue(health["files_ok"])
        self.assertEqual(health["version"], "2-10-289-1636")

    def test_verify_system_wide_health_unhealthy_on_misalignment(self):
        self.installer_file.write_text(
            '#define AppVersion "2-01-001-0000"\n'
            '#define VersionInfoVersion "2.01.001.0000"\n',
            encoding="utf-8"
        )
        health = verify_system_wide_health(self.root)
        self.assertEqual(health["status"], "UNHEALTHY")
        self.assertFalse(health["version_aligned"])

    def test_run_full_validation_cycle_skip_tests(self):
        res = run_full_validation_cycle(self.root, skip_tests=True)
        self.assertTrue(res["passed"])
        self.assertTrue(res["version_aligned"])
        self.assertTrue(res["files_ok"])
        self.assertTrue(res["tests_ok"])

    def test_telemetry_tracking(self):
        tel_before = get_build_validation_telemetry()
        cycles_before = tel_before["validation_cycles_count"]

        run_full_validation_cycle(self.root, skip_tests=True)

        tel_after = get_build_validation_telemetry()
        self.assertEqual(tel_after["validation_cycles_count"], cycles_before + 1)
        self.assertGreaterEqual(tel_after["pass_rate_pct"], 0.0)

    @patch("sys.exit")
    @patch("tools.build_validator.PROJECT_ROOT")
    def test_main_cli_alignment_only(self, mock_project_root, mock_exit):
        mock_project_root.__truediv__.side_effect = self.root.__truediv__
        main(["--alignment-only", "--json"])
        mock_exit.assert_called_with(0)

    @patch("sys.exit")
    @patch("tools.build_validator.PROJECT_ROOT")
    def test_main_cli_skip_tests(self, mock_project_root, mock_exit):
        mock_project_root.__truediv__.side_effect = self.root.__truediv__
        main(["--skip-tests", "--json"])
        mock_exit.assert_called_with(0)


if __name__ == "__main__":
    unittest.main()
