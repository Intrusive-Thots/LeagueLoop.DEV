"""
Unit tests for `src/core/version.py`.

Tests version string formatting, component validation, and agreement
with version bump tooling (`tools/bump_version.py`).
"""

import os
import re
import subprocess
import sys
import unittest

from core.version import __version__
from tools import bump_version


class TestVersion(unittest.TestCase):
    def test_version_is_non_empty_string(self):
        """Ensure __version__ exists and is a non-empty string."""
        self.assertIsInstance(__version__, str)
        self.assertTrue(len(__version__) > 0)

    def test_version_format_regex(self):
        """Ensure __version__ matches format major-month-days_left-HHMM."""
        pattern = r"^\d-\d{2}-\d{1,3}-\d{4}$"
        self.assertIsNotNone(
            re.match(pattern, __version__),
            f"__version__ '{__version__}' does not match pattern '{pattern}'",
        )

    def test_version_major_is_two(self):
        """Ensure major version is 2."""
        self.assertTrue(
            __version__.startswith("2-"),
            f"Expected major version 2, got '{__version__}'",
        )

    def test_version_components_validity(self):
        """Validate individual numeric components of __version__."""
        parts = __version__.split("-")
        self.assertEqual(len(parts), 4, f"Expected 4 parts in version string, got {len(parts)}")

        major, month_str, days_left_str, time_str = parts

        self.assertEqual(major, "2")

        month = int(month_str)
        self.assertTrue(1 <= month <= 12, f"Month out of range: {month}")

        days_left = int(days_left_str)
        self.assertTrue(0 <= days_left <= 366, f"Days remaining out of range: {days_left}")

        self.assertEqual(len(time_str), 4, f"Time string should be 4 digits: {time_str}")
        hour = int(time_str[:2])
        minute = int(time_str[2:])

        self.assertTrue(0 <= hour <= 23, f"Hour out of range: {hour}")
        self.assertTrue(0 <= minute <= 59, f"Minute out of range: {minute}")

    def test_bump_version_tool_read_version(self):
        """Ensure tools/bump_version.py read_version() returns __version__."""
        read_val = bump_version.read_version()
        self.assertEqual(read_val, __version__)

    def test_bump_version_check_command(self):
        """Ensure `python tools/bump_version.py --check` passes."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            [sys.executable, os.path.join(root, "tools", "bump_version.py"), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"bump_version.py --check failed: {result.stdout}\n{result.stderr}",
        )

    def test_bump_version_current_version_format(self):
        """Ensure tools/bump_version.py current_version() generates valid version string."""
        curr = bump_version.current_version()
        pattern = r"^2-\d{2}-\d{1,3}-\d{4}$"
        self.assertIsNotNone(
            re.match(pattern, curr),
            f"Generated current_version() '{curr}' does not match pattern '{pattern}'",
        )


if __name__ == "__main__":
    unittest.main()
