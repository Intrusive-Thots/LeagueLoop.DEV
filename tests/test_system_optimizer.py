"""
Unit tests for SystemOptimizer service and SettingsActionRow UI component.
"""
import unittest
from unittest.mock import MagicMock, patch

from services.system_optimizer import (
    PROTECTED_PROCESS_NAMES,
    TARGET_PROCESS_NAMES,
    SystemOptimizer,
)


class TestSystemOptimizer(unittest.TestCase):
    def test_target_and_protected_sets_disjoint(self):
        """No target process to kill should ever be in the protected set."""
        overlap = TARGET_PROCESS_NAMES.intersection(PROTECTED_PROCESS_NAMES)
        self.assertEqual(overlap, set(), f"Target and protected processes must not overlap: {overlap}")

    def test_critical_processes_protected(self):
        """Verify critical game and operating system processes are explicitly protected."""
        critical = [
            "explorer.exe",
            "leagueclient.exe",
            "league of legends.exe",
            "python.exe",
            "pythonw.exe",
            "vgc.exe",
            "dwm.exe",
            "system",
        ]
        for name in critical:
            self.assertIn(name, PROTECTED_PROCESS_NAMES)

    @patch("services.system_optimizer.psutil.process_iter")
    def test_kill_unnecessary_processes_filtering(self, mock_process_iter):
        """Ensure only non-protected target processes are terminated."""
        mock_onedrive = MagicMock()
        mock_onedrive.info = {
            "pid": 1234,
            "name": "OneDrive.exe",
            "memory_info": MagicMock(rss=50 * 1024 * 1024),
        }

        mock_league = MagicMock()
        mock_league.info = {
            "pid": 5678,
            "name": "LeagueClient.exe",
            "memory_info": MagicMock(rss=500 * 1024 * 1024),
        }

        mock_system = MagicMock()
        mock_system.info = {
            "pid": 4,
            "name": "System",
            "memory_info": MagicMock(rss=10 * 1024 * 1024),
        }

        mock_process_iter.return_value = [mock_onedrive, mock_league, mock_system]

        result = SystemOptimizer.kill_unnecessary_processes()

        self.assertTrue(result["success"])
        self.assertEqual(result["killed_count"], 1)
        self.assertEqual(result["freed_mb"], 50.0)
        self.assertEqual(result["killed_names"], ["OneDrive.exe"])

        mock_onedrive.terminate.assert_called_once()
        mock_league.terminate.assert_not_called()
        mock_system.terminate.assert_not_called()

    @patch("services.system_optimizer.SystemOptimizer.is_windows", return_value=True)
    @patch("services.system_optimizer.SystemOptimizer.is_admin", return_value=True)
    @patch("services.system_optimizer.subprocess.run")
    def test_fix_ping_elevated(self, mock_run, mock_admin, mock_win):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc

        result = SystemOptimizer.fix_ping()
        self.assertTrue(result["success"])
        self.assertTrue(result["elevated"])
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "powershell")
        self.assertIn("1428", call_args[5])
        self.assertIn("1.1.1.1", call_args[5])

    @patch("services.system_optimizer.SystemOptimizer.is_windows", return_value=True)
    @patch("services.system_optimizer.SystemOptimizer.is_admin", return_value=False)
    @patch("services.system_optimizer.subprocess.Popen")
    def test_fix_ping_requests_elevation(self, mock_popen, mock_admin, mock_win):
        result = SystemOptimizer.fix_ping()
        self.assertTrue(result["success"])
        self.assertFalse(result["elevated"])
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        self.assertIn("-Verb RunAs", call_args[3])


if __name__ == "__main__":
    unittest.main()
