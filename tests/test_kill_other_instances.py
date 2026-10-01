import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Only stub out UI/OS-dependent modules if they cannot be imported in the test environment
for _mod in ("customtkinter", "keyboard", "pystray", "tkinterdnd2", "PIL", "PIL.Image", "PIL.ImageTk"):
    try:
        __import__(_mod)
    except Exception:
        sys.modules[_mod] = MagicMock()


from core.main import _get_install_root, _is_our_entry_point, _kill_other_instances


class DummyProc:
    def __init__(self, pid, name, cmdline=None, exe=None, cwd=None):
        self.pid = pid
        self._name = name
        self._cmdline = cmdline or []
        self._exe = exe
        self._cwd = cwd
        self.info = {
            "pid": pid,
            "name": name,
            "cmdline": self._cmdline,
            "exe": self._exe,
        }
        self.terminated = False
        self.killed = False

    def name(self):
        return self._name

    def cmdline(self):
        return self._cmdline

    def exe(self):
        return self._exe

    def cwd(self):
        return self._cwd

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class TestKillOtherInstances(unittest.TestCase):
    def setUp(self):
        self.root = os.path.abspath("/app/LeagueLoop")
        self.run_py = os.path.join(self.root, "run.py")
        self.main_py = os.path.join(self.root, "src", "core", "main.py")
        self.exe_path = os.path.join(self.root, "LeagueLoop.exe")

    def test_positive_match_run_py(self):
        proc = DummyProc(101, "python.exe", ["python", self.run_py])
        self.assertTrue(_is_our_entry_point(proc, self.root))

    def test_positive_match_main_py(self):
        proc = DummyProc(102, "python.exe", ["python", self.main_py])
        self.assertTrue(_is_our_entry_point(proc, self.root))

    def test_positive_match_relative_run_py(self):
        proc = DummyProc(103, "python.exe", ["python", "run.py"], cwd=self.root)
        self.assertTrue(_is_our_entry_point(proc, self.root))

    def test_positive_match_exe(self):
        proc = DummyProc(104, "LeagueLoop.exe", ["LeagueLoop.exe"], exe=self.exe_path)
        self.assertTrue(_is_our_entry_point(proc, self.root))

    def test_negative_match_unrelated_run_py(self):
        unrelated_run = os.path.abspath("/other/project/run.py")
        proc = DummyProc(201, "python.exe", ["python", unrelated_run])
        self.assertFalse(_is_our_entry_point(proc, self.root))

    def test_negative_match_unrelated_main_py(self):
        unrelated_main = os.path.abspath("/django/app/main.py")
        proc = DummyProc(202, "python.exe", ["python", unrelated_main])
        self.assertFalse(_is_our_entry_point(proc, self.root))

    def test_negative_match_module_core_main_unrelated(self):
        proc = DummyProc(203, "python.exe", ["python", "-m", "core.main"])
        self.assertFalse(_is_our_entry_point(proc, self.root))

    def test_negative_match_lookalike_sibling_directory(self):
        sibling_run = os.path.abspath("/app/LeagueLoop-backup/run.py")
        proc = DummyProc(204, "python.exe", ["python", sibling_run])
        self.assertFalse(_is_our_entry_point(proc, self.root))

    def test_negative_match_different_install_exe(self):
        other_exe = os.path.abspath("/other/LeagueLoop/LeagueLoop.exe")
        proc = DummyProc(205, "LeagueLoop.exe", ["LeagueLoop.exe"], exe=other_exe)
        self.assertFalse(_is_our_entry_point(proc, self.root))

    def test_negative_match_non_python_process(self):
        proc = DummyProc(206, "chrome.exe", ["chrome.exe", "http://example.com"])
        self.assertFalse(_is_our_entry_point(proc, self.root))

    def test_frozen_run_install_root(self):
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", "/opt/LeagueLoop/LeagueLoop.exe"):
            root = _get_install_root()
            self.assertEqual(os.path.normcase(root), os.path.normcase(os.path.abspath("/opt/LeagueLoop")))

    def test_kill_other_instances_execution_flow(self):
        proc_me = DummyProc(os.getpid(), "python.exe", ["python", self.run_py])
        proc_target = DummyProc(999, "python.exe", ["python", self.run_py])
        proc_other = DummyProc(888, "python.exe", ["python", "/other/run.py"])

        procs = [proc_me, proc_target, proc_other]

        mock_psutil_proc = MagicMock()
        mock_psutil_proc.pid = os.getpid()
        mock_psutil_proc.parents.return_value = []

        with patch("psutil.Process", return_value=mock_psutil_proc), \
             patch("psutil.process_iter", return_value=procs), \
             patch("psutil.wait_procs", return_value=([proc_target], [])) as mock_wait, \
             patch("core.main._get_install_root", return_value=self.root), \
             patch("utils.logger.Logger.info") as mock_info:

            _kill_other_instances()

            self.assertTrue(proc_target.terminated)
            self.assertFalse(proc_other.terminated)
            mock_wait.assert_called_once_with([proc_target], timeout=5)
            mock_info.assert_called_once()

    def test_kill_other_instances_escalates_to_kill_if_alive(self):
        proc_me = DummyProc(os.getpid(), "python.exe", ["python", self.run_py])
        proc_stubborn = DummyProc(999, "python.exe", ["python", self.run_py])

        procs = [proc_me, proc_stubborn]

        mock_psutil_proc = MagicMock()
        mock_psutil_proc.pid = os.getpid()
        mock_psutil_proc.parents.return_value = []

        with patch("psutil.Process", return_value=mock_psutil_proc), \
             patch("psutil.process_iter", return_value=procs), \
             patch("psutil.wait_procs", return_value=((), [proc_stubborn])), \
             patch("core.main._get_install_root", return_value=self.root):

            _kill_other_instances()

            self.assertTrue(proc_stubborn.terminated)
            self.assertTrue(proc_stubborn.killed)

    def test_kill_other_instances_ignores_parent_processes(self):
        parent_pid = 500
        proc_parent = DummyProc(parent_pid, "python.exe", ["python", self.run_py])
        proc_target = DummyProc(999, "python.exe", ["python", self.run_py])

        procs = [proc_parent, proc_target]

        mock_parent = MagicMock()
        mock_parent.pid = parent_pid

        mock_psutil_proc = MagicMock()
        mock_psutil_proc.pid = os.getpid()
        mock_psutil_proc.parents.return_value = [mock_parent]

        with patch("psutil.Process", return_value=mock_psutil_proc), \
             patch("psutil.process_iter", return_value=procs), \
             patch("psutil.wait_procs", return_value=([proc_target], [])), \
             patch("core.main._get_install_root", return_value=self.root):

            _kill_other_instances()

            self.assertFalse(proc_parent.terminated)
            self.assertTrue(proc_target.terminated)


if __name__ == "__main__":
    unittest.main()
