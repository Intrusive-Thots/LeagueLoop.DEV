"""
User data lives in one place, and it is not the repository.

`get_data_dir()` returned `os.path.abspath(".")` when running from source and
AppData only when frozen. On this machine that produced two live sets:

    repo/config.json      2026-09-08 05:06   93 keys   <- what dev runs used
    AppData/config.json   2026-09-01 16:04   85 keys
    repo/accounts.json    2026-09-08 04:40   2 accounts
    AppData/accounts.json 2026-08-31 15:14   1 account

Neither knew about the other, so an account added in a dev run was invisible
to the installed build. Worse, `accounts.json` sat in the working tree and
`.gitignore` did not exclude it: it happened never to have been committed, but
`tools/remove_qt_shell.bat` runs `git add -A`, which would have pushed the
account store to GitHub.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class DataDirTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_it_never_returns_the_working_directory(self):
        """The whole bug in one assertion."""
        from utils.path_utils import get_data_dir

        os.environ["LOCALAPPDATA"] = self.tmp
        here = os.getcwd()
        try:
            os.chdir(self.tmp)
            self.assertNotEqual(
                os.path.abspath(get_data_dir()), os.path.abspath(os.getcwd())
            )
        finally:
            os.chdir(here)

    def test_it_is_the_same_place_frozen_or_from_source(self):
        import sys

        from utils.path_utils import get_data_dir

        os.environ["LOCALAPPDATA"] = self.tmp
        from_source = get_data_dir()
        sys.frozen = True
        try:
            frozen = get_data_dir()
        finally:
            del sys.frozen
        self.assertEqual(from_source, frozen)

    def test_it_is_never_inside_the_repository(self):
        from utils.path_utils import get_data_dir

        os.environ["LOCALAPPDATA"] = self.tmp
        self.assertFalse(
            Path(get_data_dir()).resolve().is_relative_to(ROOT),
            "user data would sit in the working tree",
        )

    def test_the_directory_is_created(self):
        from utils.path_utils import get_data_dir

        os.environ["LOCALAPPDATA"] = self.tmp
        self.assertTrue(os.path.isdir(get_data_dir()))


class MigrationTests(unittest.TestCase):
    """The repository copy was the newer one here, so losing it would have
    looked like the app forgetting every account."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._env = dict(os.environ)
        os.environ["LOCALAPPDATA"] = self.tmp
        import utils.path_utils as pu

        self.pu = pu
        self._real_root = pu._PROJECT_ROOT
        self.fake_repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.fake_repo)
        pu._PROJECT_ROOT = self.fake_repo

    def tearDown(self):
        self.pu._PROJECT_ROOT = self._real_root
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, path, payload, mtime=None):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        if mtime:
            os.utime(path, (mtime, mtime))

    def test_a_repo_file_is_moved_into_appdata(self):
        self._write(os.path.join(self.fake_repo, "accounts.json"), {"accounts": [1, 2]})
        moved = self.pu.migrate_data_from_project_root()

        self.assertIn("accounts.json", moved)
        target = os.path.join(self.pu.get_data_dir(), "accounts.json")
        with open(target, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["accounts"], [1, 2])

    def test_the_repo_copy_is_left_behind_renamed_not_deleted(self):
        """Moving somebody's only account store had better be reversible."""
        source = os.path.join(self.fake_repo, "accounts.json")
        self._write(source, {"accounts": [1]})
        self.pu.migrate_data_from_project_root()

        self.assertFalse(os.path.exists(source))
        self.assertTrue(os.path.exists(source + ".moved-to-appdata"))

    def test_the_newer_copy_wins(self):
        """On this machine the repo copy was a week newer and had two accounts
        against AppData's one."""
        target_dir = self.pu.get_data_dir()
        self._write(os.path.join(target_dir, "accounts.json"), {"accounts": [1]}, mtime=1000)
        self._write(os.path.join(self.fake_repo, "accounts.json"), {"accounts": [1, 2]}, mtime=9000)

        self.pu.migrate_data_from_project_root()
        with open(os.path.join(target_dir, "accounts.json"), encoding="utf-8") as f:
            result = json.load(f)
        self.assertEqual(result["accounts"], [1, 2])

    def test_a_newer_appdata_copy_is_not_overwritten(self):
        target_dir = self.pu.get_data_dir()
        self._write(os.path.join(target_dir, "accounts.json"), {"accounts": [9]}, mtime=9000)
        self._write(os.path.join(self.fake_repo, "accounts.json"), {"accounts": [1]}, mtime=1000)

        self.pu.migrate_data_from_project_root()
        with open(os.path.join(target_dir, "accounts.json"), encoding="utf-8") as f:
            result = json.load(f)
        self.assertEqual(result["accounts"], [9])


    def test_an_overwritten_copy_is_kept_as_superseded(self):
        target_dir = self.pu.get_data_dir()
        self._write(os.path.join(target_dir, "accounts.json"), {"accounts": [9]}, mtime=1000)
        self._write(os.path.join(self.fake_repo, "accounts.json"), {"accounts": [1]}, mtime=9000)

        self.pu.migrate_data_from_project_root()
        self.assertTrue(
            os.path.exists(os.path.join(target_dir, "accounts.json.superseded"))
        )

    def test_the_sessions_folder_moves_too(self):
        slot = os.path.join(self.fake_repo, "sessions", "someone")
        os.makedirs(slot)
        open(os.path.join(slot, "RiotClientPrivateSettings.yaml"), "w").close()

        moved = self.pu.migrate_data_from_project_root()
        self.assertIn("sessions/", moved)
        self.assertTrue(os.path.isdir(os.path.join(self.pu.get_data_dir(), "sessions")))

    def test_a_clean_repository_migrates_nothing(self):
        self.assertEqual(self.pu.migrate_data_from_project_root(), [])

    def test_running_it_twice_is_harmless(self):
        self._write(os.path.join(self.fake_repo, "config.json"), {"a": 1})
        self.pu.migrate_data_from_project_root()
        self.assertEqual(self.pu.migrate_data_from_project_root(), [])


class GitignoreTests(unittest.TestCase):
    """It was wrapped in ``` markdown fences, which git reads as a literal
    pattern — and it never excluded the data files at all."""

    def setUp(self):
        self.body = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.patterns = {
            line.strip() for line in self.body.splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

    def test_no_markdown_fences(self):
        self.assertNotIn("```", self.body)

    def test_the_account_store_can_never_be_committed(self):
        for name in ("accounts.json", "config.json", "leagueloop.db", "sessions/"):
            self.assertIn(name, self.patterns, name)

    def test_the_migration_leftovers_are_ignored(self):
        self.assertIn("*.moved-to-appdata", self.patterns)


if __name__ == "__main__":
    unittest.main()
