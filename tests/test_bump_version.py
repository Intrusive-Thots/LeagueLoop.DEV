"""
test_bump_version.py — Unit tests for tools.bump_version

Validates version string generation, hyphen-to-dot Inno Setup transformation,
installer.iss synchronization, and version alignment integrity verification.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.bump_version import (
    MAJOR,
    current_version,
    to_version_info,
    read_version,
    write_version,
    read_installer_versions,
    write_installer_versions,
    check_version_alignment,
    main,
)


class TestBumpVersion(unittest.TestCase):
    def test_current_version_format(self):
        ver = current_version()
        parts = ver.split("-")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], str(MAJOR))
        self.assertTrue(parts[1].isdigit())
        self.assertTrue(parts[2].isdigit())
        self.assertTrue(parts[3].isdigit())

    def test_to_version_info(self):
        self.assertEqual(to_version_info("2-10-287-1752"), "2.10.287.1752")
        self.assertEqual(to_version_info("2-01-001-1200"), "2.01.001.1200")

    def test_read_and_write_version(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f:
            f.write('__version__ = "2-10-100-1000"\n')
            temp_path = f.name

        try:
            val = read_version(temp_path)
            self.assertEqual(val, "2-10-100-1000")

            write_version("2-10-100-1001", temp_path)
            new_val = read_version(temp_path)
            self.assertEqual(new_val, "2-10-100-1001")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_read_and_write_installer_versions(self):
        iss_content = (
            '; Installer script\n'
            '#define AppVersion "2-10-100-1000"\n'
            '#define VersionInfoVersion "2.10.100.1000"\n'
            '[Setup]\n'
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f:
            f.write(iss_content)
            temp_path = f.name

        try:
            app_ver, info_ver = read_installer_versions(temp_path)
            self.assertEqual(app_ver, "2-10-100-1000")
            self.assertEqual(info_ver, "2.10.100.1000")

            write_installer_versions("2-10-200-2000", temp_path)
            new_app, new_info = read_installer_versions(temp_path)
            self.assertEqual(new_app, "2-10-200-2000")
            self.assertEqual(new_info, "2.10.200.2000")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_check_version_alignment_success(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f_ver:
            f_ver.write('__version__ = "2-10-100-1000"\n')
            ver_path = f_ver.name

        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f_iss:
            f_iss.write(
                '#define AppVersion "2-10-100-1000"\n'
                '#define VersionInfoVersion "2.10.100.1000"\n'
            )
            iss_path = f_iss.name

        try:
            ok, msg = check_version_alignment(ver_path, iss_path)
            self.assertTrue(ok)
            self.assertIn("aligned", msg)
        finally:
            Path(ver_path).unlink(missing_ok=True)
            Path(iss_path).unlink(missing_ok=True)

    def test_check_version_alignment_mismatch(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f_ver:
            f_ver.write('__version__ = "2-10-100-1000"\n')
            ver_path = f_ver.name

        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f_iss:
            f_iss.write(
                '#define AppVersion "2-10-100-9999"\n'
                '#define VersionInfoVersion "2.10.100.9999"\n'
            )
            iss_path = f_iss.name

        try:
            ok, msg = check_version_alignment(ver_path, iss_path)
            self.assertFalse(ok)
            self.assertIn("does not match", msg)
        finally:
            Path(ver_path).unlink(missing_ok=True)
            Path(iss_path).unlink(missing_ok=True)

    def test_main_cli_check_success(self):
        with patch("tools.bump_version.check_version_alignment", return_value=(True, "All good")):
            with patch("sys.stdout"):
                code = main(["--check"])
                self.assertEqual(code, 0)

    def test_main_cli_check_failure(self):
        with patch("tools.bump_version.check_version_alignment", return_value=(False, "Mismatch")):
            with patch("sys.stdout"):
                code = main(["--check"])
                self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
