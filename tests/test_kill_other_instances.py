"""`_kill_other_instances()` must terminate this install and nothing else.

It ran before the app was constructed and matched any process whose command
line ended in `run.py` **or `main.py`** — two of the most common script names
there are. On a development machine that is a wide net: an unrelated
checkout's `run.py`, a Django `main.py`, a scratch script in another
directory. All of them were terminated silently, before LeagueLoop had even
started, with the failure swallowed by a bare `except Exception`.

The function has a real job — four instances sharing one `config.json` and
`accounts.json` overwrite each other's settings and race to accept the same
ready check. These tests pin the job without the collateral.
"""

import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


class FakeProc:
    """The slice of psutil.Process this function actually touches."""

    def __init__(self, pid, name, cmdline=None, exe=None):
        self.pid = pid
        self.info = {
            "pid": pid,
            "name": name,
            "cmdline": cmdline or [],
            "exe": exe,
        }
        self.terminated = False
        self.killed = False

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def parents(self):
        return []


def _run_against(procs, root):
    """Run the real function against a fake process table."""
    from core import main as main_mod

    import psutil

    self_proc = FakeProc(os.getpid(), "python")

    with patch.object(main_mod, "_leagueloop_project_root", return_value=root), \
         patch.object(psutil, "process_iter", return_value=list(procs)), \
         patch.object(psutil, "Process", return_value=self_proc), \
         patch.object(psutil, "wait_procs", return_value=([], [])):
        main_mod._kill_other_instances()

    return [p for p in procs if p.terminated]


class KillOtherInstancesTests(unittest.TestCase):

    def setUp(self):
        self.root = os.path.normcase(os.path.abspath(os.path.join("/opt", "LeagueLoop")))
        self.our_run = os.path.join(self.root, "run.py")
        self.our_main = os.path.join(self.root, "src", "core", "main.py")

    # -------------------------------------------------- what it must kill
    def test_kills_our_own_run_py(self):
        proc = FakeProc(101, "python.exe", ["python.exe", self.our_run])
        self.assertEqual(_run_against([proc], self.root), [proc])

    def test_kills_our_own_core_main(self):
        proc = FakeProc(102, "python", ["python", self.our_main])
        self.assertEqual(_run_against([proc], self.root), [proc])

    # ------------------------------------------- what it must NOT kill
    def test_spares_an_unrelated_run_py(self):
        """The whole point. Another checkout's run.py is not ours."""
        other = os.path.join(os.sep, "home", "malcolm", "some-other-project", "run.py")
        proc = FakeProc(201, "python", ["python", other])
        self.assertEqual(_run_against([proc], self.root), [])

    def test_spares_an_unrelated_main_py(self):
        other = os.path.join(os.sep, "srv", "django-app", "main.py")
        proc = FakeProc(202, "python3", ["python3", other])
        self.assertEqual(_run_against([proc], self.root), [])

    def test_spares_a_module_invocation_of_someone_elses_core_main(self):
        """`-m core.main` used to match on the bare substring."""
        proc = FakeProc(203, "python", ["python", "-m", "core.main"])
        self.assertEqual(_run_against([proc], self.root), [])

    def test_spares_a_non_python_process_named_run_py(self):
        proc = FakeProc(204, "bash", ["bash", self.our_run])
        self.assertEqual(_run_against([proc], self.root), [])

    def test_spares_a_leagueloop_exe_from_a_different_install(self):
        other_exe = os.path.join(os.sep, "other", "install", "LeagueLoop.exe")
        proc = FakeProc(205, "LeagueLoop.exe", exe=other_exe)
        self.assertEqual(_run_against([proc], self.root), [])

    def test_kills_a_leagueloop_exe_from_this_install(self):
        our_exe = os.path.join(self.root, "LeagueLoop.exe")
        proc = FakeProc(206, "LeagueLoop.exe", exe=our_exe)
        self.assertEqual(_run_against([proc], self.root), [proc])

    # -------------------------------------------------------- mixed table
    def test_picks_only_ours_out_of_a_realistic_process_table(self):
        ours = FakeProc(1, "python", ["python", self.our_run])
        theirs = [
            FakeProc(2, "python", ["python", "/home/m/blog/run.py"]),
            FakeProc(3, "python", ["python", "/home/m/api/main.py"]),
            FakeProc(4, "chrome", ["chrome"]),
            FakeProc(5, "python", ["python", "-c", "print('run.py')"]),
        ]
        killed = _run_against([ours] + theirs, self.root)
        self.assertEqual(killed, [ours])


class EntryPointMatchTests(unittest.TestCase):
    """`_is_our_entry_point` in isolation — it is the whole safety property."""

    def setUp(self):
        from core.main import _is_our_entry_point
        self.match = _is_our_entry_point
        self.root = os.path.normcase(os.path.abspath(os.path.join("/opt", "LeagueLoop")))

    def test_accepts_our_paths(self):
        self.assertTrue(self.match(os.path.join(self.root, "run.py"), self.root))
        self.assertTrue(
            self.match(os.path.join(self.root, "src", "core", "main.py"), self.root)
        )

    def test_rejects_same_basename_elsewhere(self):
        self.assertFalse(self.match("/elsewhere/run.py", self.root))
        self.assertFalse(self.match("/elsewhere/src/core/main.py", self.root))

    def test_rejects_a_lookalike_sibling_directory(self):
        """`/opt/LeagueLoop-backup/run.py` must not read as `/opt/LeagueLoop`."""
        sibling = self.root + "-backup"
        self.assertFalse(self.match(os.path.join(sibling, "run.py"), self.root))

    def test_rejects_other_scripts_inside_our_root(self):
        self.assertFalse(
            self.match(os.path.join(self.root, "tools", "check_accounts.py"), self.root)
        )

    def test_survives_a_junk_argument(self):
        for junk in ("", "\0", "--flag", "-m"):
            self.assertFalse(self.match(junk, self.root))


if __name__ == "__main__":
    unittest.main()
