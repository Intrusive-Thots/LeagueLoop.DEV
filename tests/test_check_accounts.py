"""
test_check_accounts.py — Comprehensive unit tests for tools/check_accounts.py.
Validates read-only preflight diagnostics, JSON serialization, and CLI invocation.
"""

import json
import io
import unittest
from unittest.mock import MagicMock, patch

from tools.check_accounts import (
    line,
    run_account_preflight,
    preflight,
    main,
    OK,
    WARN,
    FAIL,
)


class TestCheckAccounts(unittest.TestCase):
    def setUp(self):
        self.mock_manager = MagicMock()
        self.mock_switcher = MagicMock()
        self.mock_switcher.phase.value = "idle"
        self.mock_switcher.busy = False
        self.mock_manager._switcher = self.mock_switcher
        self.mock_manager.riot_client = MagicMock()

        self.mock_accounts = [
            {"label": "Account 1", "username": "player1"},
            {"label": "Account 2", "username": "player2"},
        ]
        self.mock_manager.get_accounts.return_value = self.mock_accounts
        self.mock_manager.get_default_account_index.return_value = 0
        self.mock_manager.get_password.side_effect = lambda idx: "secret"

    def test_line_formatter(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            line(OK, "test message")
        self.assertIn("  OK   test message", buf.getvalue())

    @patch("services.accounts.RiotSession")
    def test_run_account_preflight_clean(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.client_running.return_value = True
        mock_session.connect.return_value = True
        mock_session.is_signed_in.return_value = True
        mock_session.current_login_name.return_value = "player1"
        mock_session_cls.return_value = mock_session

        res = run_account_preflight(manager=self.mock_manager)

        self.assertEqual(res["status"], "HEALTHY")
        self.assertEqual(res["problems_count"], 0)
        self.assertTrue(res["switcher_wired"])
        self.assertEqual(res["switcher_phase"], "idle")
        self.assertFalse(res["switcher_busy"])
        self.assertTrue(res["riot_client_running"])
        self.assertTrue(res["api_reachable"])
        self.assertTrue(res["signed_in"])
        self.assertEqual(res["current_user"], "player1")
        self.assertEqual(res["accounts_count"], 2)
        self.assertTrue(res["accounts"][0]["is_active"])
        self.assertTrue(res["accounts"][0]["is_default"])
        self.assertFalse(res["accounts"][1]["is_active"])

    @patch("services.accounts.RiotSession")
    def test_run_account_preflight_client_offline(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.client_running.return_value = False
        mock_session.connect.return_value = False
        mock_session_cls.return_value = mock_session

        res = run_account_preflight(manager=self.mock_manager)

        self.assertEqual(res["status"], "ATTENTION_REQUIRED")
        self.assertGreaterEqual(res["problems_count"], 1)
        self.assertFalse(res["riot_client_running"])
        self.assertFalse(res["api_reachable"])

    @patch("services.accounts.RiotSession")
    def test_run_account_preflight_no_switcher(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.client_running.return_value = True
        mock_session.connect.return_value = True
        mock_session.is_signed_in.return_value = False
        mock_session_cls.return_value = mock_session

        self.mock_manager._switcher = None
        res = run_account_preflight(manager=self.mock_manager)

        self.assertFalse(res["switcher_wired"])
        self.assertEqual(res["switcher_phase"], "unavailable")
        self.assertGreaterEqual(res["problems_count"], 1)

    @patch("services.accounts.RiotSession")
    def test_run_account_preflight_missing_password(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.client_running.return_value = True
        mock_session.connect.return_value = True
        mock_session_cls.return_value = mock_session

        self.mock_manager.get_password.side_effect = Exception("No password")
        res = run_account_preflight(manager=self.mock_manager)

        self.assertGreaterEqual(res["problems_count"], 2)
        self.assertFalse(res["accounts"][0]["has_password"])

    @patch("services.accounts.RiotSession")
    def test_preflight_json_output(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.client_running.return_value = True
        mock_session.connect.return_value = True
        mock_session.is_signed_in.return_value = True
        mock_session.current_login_name.return_value = "player1"
        mock_session_cls.return_value = mock_session

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = preflight(as_json=True, manager=self.mock_manager)

        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["status"], "HEALTHY")
        self.assertEqual(data["accounts_count"], 2)

    @patch("services.accounts.RiotSession")
    def test_preflight_formatted_output(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.client_running.return_value = True
        mock_session.connect.return_value = True
        mock_session.is_signed_in.return_value = True
        mock_session.current_login_name.return_value = "player1"
        mock_session_cls.return_value = mock_session

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = preflight(as_json=False, manager=self.mock_manager)

        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("LeagueLoop - account switching preflight", output)
        self.assertIn("Preflight clean", output)

    @patch("tools.check_accounts.preflight", return_value=0)
    def test_main_cli_json_flag(self, mock_preflight):
        res = main(["--json"])
        self.assertEqual(res, 0)
        mock_preflight.assert_called_with(as_json=True)

    @patch("tools.check_accounts.do_switch", return_value=0)
    def test_main_cli_switch_flag(self, mock_switch):
        res = main(["--switch", "1"])
        self.assertEqual(res, 0)
        mock_switch.assert_called_with(1)

    @patch("tools.check_accounts.do_sign_out", return_value=0)
    def test_main_cli_sign_out_flag(self, mock_sign_out):
        res = main(["--sign-out"])
        self.assertEqual(res, 0)
        mock_sign_out.assert_called_once()

    @patch("tools.check_accounts.do_round_trip", return_value=0)
    def test_main_cli_round_trip_flag(self, mock_round_trip):
        res = main(["--round-trip"])
        self.assertEqual(res, 0)
        mock_round_trip.assert_called_once()


if __name__ == "__main__":
    unittest.main()
