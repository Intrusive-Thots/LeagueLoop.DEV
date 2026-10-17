"""
Unit tests for src/utils/path_utils.py.

Tests cover:
- get_asset_path: default execution vs sys._MEIPASS frozen execution.
- get_data_dir: LOCALAPPDATA / APPDATA env var usage and fallback to ~/.local/share.
- migrate_data_from_project_root: data file & directory migration logic, error handling,
  and handling of existing/superseded destination files.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.path_utils import (
    _PROJECT_ROOT,
    get_asset_path,
    get_data_dir,
    migrate_data_from_project_root,
)


class TestGetAssetPath(unittest.TestCase):
    def test_get_asset_path_default(self):
        relative = "assets/icon.png"
        expected = os.path.join(_PROJECT_ROOT, relative)
        self.assertEqual(get_asset_path(relative), expected)

    def test_get_asset_path_frozen(self):
        fake_meipass = "/tmp/fake_meipass_folder"
        relative = "assets/icon.png"
        with patch.object(sys, "_MEIPASS", fake_meipass, create=True):
            expected = os.path.join(fake_meipass, relative)
            self.assertEqual(get_asset_path(relative), expected)


class TestGetDataDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env_patcher = patch.dict(os.environ, clear=True)
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_get_data_dir_with_localappdata(self):
        os.environ["LOCALAPPDATA"] = self.tmp
        expected = os.path.join(self.tmp, "LeagueLoop")
        result = get_data_dir()
        self.assertEqual(result, expected)
        self.assertTrue(os.path.isdir(result))

    def test_get_data_dir_with_appdata(self):
        os.environ["APPDATA"] = self.tmp
        expected = os.path.join(self.tmp, "LeagueLoop")
        result = get_data_dir()
        self.assertEqual(result, expected)
        self.assertTrue(os.path.isdir(result))

    def test_get_data_dir_fallback_non_windows(self):
        # Clear both LOCALAPPDATA and APPDATA
        os.environ.pop("LOCALAPPDATA", None)
        os.environ.pop("APPDATA", None)
        expected = os.path.join(os.path.expanduser("~"), ".local", "share", "LeagueLoop")
        result = get_data_dir()
        self.assertEqual(result, expected)
        self.assertTrue(os.path.isdir(result))


class TestMigrateDataFromProjectRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fake_repo = os.path.join(self.tmp, "repo")
        self.fake_appdata = os.path.join(self.tmp, "appdata")
        os.makedirs(self.fake_repo)
        os.makedirs(self.fake_appdata)

        self.env_patcher = patch.dict(os.environ, {"LOCALAPPDATA": self.fake_appdata})
        self.env_patcher.start()

        import utils.path_utils as pu
        self.pu = pu
        self.real_root = pu._PROJECT_ROOT
        pu._PROJECT_ROOT = self.fake_repo

    def tearDown(self):
        self.pu._PROJECT_ROOT = self.real_root
        self.env_patcher.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_migrate_file_success(self):
        source_file = os.path.join(self.fake_repo, "config.json")
        with open(source_file, "w", encoding="utf-8") as f:
            f.write('{"key": "value"}')

        moved = migrate_data_from_project_root()
        self.assertIn("config.json", moved)

        dest_file = os.path.join(get_data_dir(), "config.json")
        self.assertTrue(os.path.exists(dest_file))
        self.assertTrue(os.path.exists(source_file + ".moved-to-appdata"))
        self.assertFalse(os.path.exists(source_file))

    def test_migrate_file_destination_newer(self):
        source_file = os.path.join(self.fake_repo, "config.json")
        dest_file = os.path.join(get_data_dir(), "config.json")

        with open(source_file, "w", encoding="utf-8") as f:
            f.write('{"source": True}')
        os.utime(source_file, (1000, 1000))

        with open(dest_file, "w", encoding="utf-8") as f:
            f.write('{"dest": True}')
        os.utime(dest_file, (2000, 2000))

        moved = migrate_data_from_project_root()
        self.assertNotIn("config.json", moved)
        with open(dest_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('"dest": True', content)

    def test_migrate_file_destination_older_creates_superseded(self):
        source_file = os.path.join(self.fake_repo, "config.json")
        dest_file = os.path.join(get_data_dir(), "config.json")

        with open(source_file, "w", encoding="utf-8") as f:
            f.write('{"source": True}')
        os.utime(source_file, (2000, 2000))

        with open(dest_file, "w", encoding="utf-8") as f:
            f.write('{"dest": True}')
        os.utime(dest_file, (1000, 1000))

        moved = migrate_data_from_project_root()
        self.assertIn("config.json", moved)
        self.assertTrue(os.path.exists(dest_file + ".superseded"))

    def test_migrate_directory_success(self):
        source_dir = os.path.join(self.fake_repo, "sessions")
        os.makedirs(source_dir)
        session_file = os.path.join(source_dir, "session.txt")
        with open(session_file, "w", encoding="utf-8") as f:
            f.write("session data")

        moved = migrate_data_from_project_root()
        self.assertIn("sessions/", moved)

        dest_dir = os.path.join(get_data_dir(), "sessions")
        self.assertTrue(os.path.isdir(dest_dir))
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "session.txt")))
        self.assertTrue(os.path.exists(source_dir + ".moved-to-appdata"))

    def test_migrate_file_oserror_handled(self):
        source_file = os.path.join(self.fake_repo, "config.json")
        with open(source_file, "w", encoding="utf-8") as f:
            f.write('{"key": "value"}')

        with patch("shutil.copy2", side_effect=OSError("Permission denied")):
            moved = migrate_data_from_project_root()
            self.assertEqual(moved, [])


if __name__ == "__main__":
    unittest.main()
