"""
Unit tests for AccountSwitcher in src/services/accounts/switcher.py
"""

import unittest
from unittest.mock import MagicMock, patch

from services.accounts.results import OP_SIGN_OUT, SwitchOutcome, SwitchPhase, SwitchResult
from services.accounts.switcher import AccountSwitcher


class TestAccountSwitcherUnit(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.vault = MagicMock()
        self.accounts = [{"label": "Main", "username": "main_user"}, {"label": "Smurf", "username": "smurf_user"}]
        self.accounts_provider = lambda: self.accounts
        self.bus = MagicMock()
        self.switcher = AccountSwitcher(
            session=self.session,
            accounts_provider=self.accounts_provider,
            vault=self.vault,
            bus=self.bus,
            sign_out_timeout_s=0.01,
            client_timeout_s=0.01,
            shutdown_timeout_s=0.05,
            settle_s=0.0,
        )

    def test_properties_phase_and_busy(self):
        self.assertEqual(self.switcher.phase, SwitchPhase.IDLE)
        self.assertFalse(self.switcher.busy)

        self.switcher._phase = SwitchPhase.PREPARING
        self.assertTrue(self.switcher.busy)

        self.switcher._phase = SwitchPhase.DONE
        self.assertFalse(self.switcher.busy)

        self.switcher._phase = SwitchPhase.FAILED
        self.assertFalse(self.switcher.busy)

    def test_emit_event_bus_exception_handled(self):
        self.bus.emit.side_effect = RuntimeError("Bus error")
        # Should not raise exception when _emit fails
        self.switcher._emit("test_channel", {"data": 123})
        self.bus.emit.assert_called_once_with("test_channel", {"data": 123})

    def test_account_key(self):
        self.assertEqual(AccountSwitcher.account_key({"username": "  User1  "}), "user1")
        self.assertEqual(AccountSwitcher.account_key({"label": "Label1"}), "label1")
        self.assertEqual(AccountSwitcher.account_key({}), "")

    def test_session_info(self):
        info_mock = MagicMock()
        self.vault.info.return_value = info_mock

        # Out of bounds index
        self.assertIsNone(self.switcher.session_info(-1))
        self.assertIsNone(self.switcher.session_info(10))

        # Valid index
        res = self.switcher.session_info(0)
        self.assertEqual(res, info_mock)
        self.vault.info.assert_called_once_with("main_user")

    def test_capture_current(self):
        self.vault.capture.return_value = True

        # Out of bounds index
        self.assertFalse(self.switcher.capture_current(-1))
        self.assertFalse(self.switcher.capture_current(10))

        # Valid index
        res = self.switcher.capture_current(1)
        self.assertTrue(res)
        self.vault.capture.assert_called_once_with("smurf_user")

    def test_switch_to_and_sign_out_when_busy(self):
        # Acquire lock manually to simulate busy switcher
        self.assertTrue(self.switcher._lock.acquire(blocking=False))
        try:
            res_switch = self.switcher.switch_to(0)
            self.assertEqual(res_switch.outcome, SwitchOutcome.BUSY)

            res_signout = self.switcher.sign_out()
            self.assertEqual(res_signout.outcome, SwitchOutcome.BUSY)
            self.assertEqual(res_signout.operation, OP_SIGN_OUT)
        finally:
            self.switcher._lock.release()

    def test_switch_to_out_of_bounds_index(self):
        res = self.switcher.switch_to(-1)
        self.assertEqual(res.outcome, SwitchOutcome.INVALID_ACCOUNT)

        res2 = self.switcher.switch_to(5)
        self.assertEqual(res2.outcome, SwitchOutcome.INVALID_ACCOUNT)

    def test_switch_to_exception_during_locked_execution(self):
        with patch.object(self.switcher, "_switch_locked", side_effect=RuntimeError("Unexpected error")):
            res = self.switcher.switch_to(0)
            self.assertEqual(res.outcome, SwitchOutcome.ERROR)
            self.assertEqual(res.detail, "RuntimeError")

    def test_sign_out_exception_during_execution(self):
        with patch.object(self.switcher, "_ensure_signed_out", side_effect=RuntimeError("Signout crash")):
            res = self.switcher.sign_out()
            self.assertEqual(res.outcome, SwitchOutcome.ERROR)
            self.assertEqual(res.detail, "RuntimeError")
            self.assertEqual(res.operation, OP_SIGN_OUT)

    def test_already_active_edge_cases(self):
        # Falsy key
        self.assertFalse(self.switcher._already_active(""))

        # session connect or is_signed_in returns False
        self.session.connect.return_value = False
        self.assertFalse(self.switcher._already_active("main_user"))

        self.session.connect.return_value = True
        self.session.is_signed_in.return_value = False
        self.assertFalse(self.switcher._already_active("main_user"))

        # Exception raised by current_login_name
        self.session.is_signed_in.return_value = True
        self.session.current_login_name.side_effect = RuntimeError("API error")
        self.assertFalse(self.switcher._already_active("main_user"))

    def test_ensure_signed_out_edge_cases(self):
        # Client unreachable
        self.session.connect.return_value = False
        self.assertEqual(self.switcher._ensure_signed_out(), SwitchOutcome.CLIENT_UNREACHABLE)

        # Client reachable but not signed in
        self.session.connect.return_value = True
        self.session.is_signed_in.return_value = False
        self.assertIsNone(self.switcher._ensure_signed_out())

        # Sign out failed timeout
        self.session.is_signed_in.return_value = True
        self.session.wait_until_signed_out.return_value = False
        self.assertEqual(self.switcher._ensure_signed_out(), SwitchOutcome.SIGN_OUT_FAILED)

    def test_safely_helper(self):
        failing_fn = MagicMock(side_effect=ValueError("Boom"))
        res = AccountSwitcher._safely(failing_fn, 1, 2)
        self.assertIsNone(res)

        working_fn = MagicMock(return_value=42)
        res2 = AccountSwitcher._safely(working_fn, "arg")
        self.assertEqual(res2, 42)

    def _credentialed(self, filler=None):
        from services.accounts.form_login import FillResult, FillStatus
        self.filler = filler or MagicMock()
        self.filler.available.return_value = True
        if filler is None:
            self.filler.fill_and_submit.return_value = FillResult(FillStatus.SUBMITTED, 1)
            self.filler.wait_for_window.return_value = 101
            self.filler.form_ready.return_value = None
            self.filler.captcha_visible.return_value = None
        self.switcher.form = self.filler
        self.switcher._password = lambda i: "pw-%d" % i

    def test_switch_without_a_password_fails_before_touching_the_client(self):
        self.switcher._password = lambda i: ""
        res = self.switcher.switch_to(0)
        self.assertEqual(res.outcome, SwitchOutcome.NO_CREDENTIALS)
        self.assertEqual(res.phase, SwitchPhase.PREPARING)
        self.session.sign_out.assert_not_called()

    def test_switch_sequence_client_wait_failure(self):
        self._credentialed()
        self.switcher._client_running = lambda: False
        self.session.wait_until_client_ready.return_value = False

        res = self.switcher.switch_to(0)
        self.assertEqual(res.outcome, SwitchOutcome.CLIENT_NOT_RUNNING)
        self.assertEqual(res.phase, SwitchPhase.WAITING_FOR_CLIENT)

    def test_switch_sequence_sign_in_screen_never_appears(self):
        self._credentialed()
        self.switcher._client_running = lambda: True
        self.switcher._sign_in_screen_timeout_s = 0.05
        self.switcher._poll_s = 0.01
        self.session.connect.return_value = True
        self.session.is_signed_in.return_value = False
        self.filler.wait_for_window.return_value = 0

        res = self.switcher.switch_to(0)
        self.assertEqual(res.outcome, SwitchOutcome.LOGIN_FORM_NOT_FOUND)
        self.filler.fill_and_submit.assert_not_called()

    def test_switch_sequence_verification_timeout(self):
        self._credentialed()
        self.switcher._client_running = lambda: True
        self.switcher._verify_timeout_s = 0.05
        self.switcher._poll_s = 0.01
        self.session.connect.return_value = True
        self.session.is_signed_in.return_value = False
        self.session.auth_state.return_value = None

        res = self.switcher.switch_to(0)
        self.assertEqual(res.outcome, SwitchOutcome.TIMED_OUT)
        self.assertEqual(res.phase, SwitchPhase.VERIFYING)
        self.assertIn("Switch again", res.message)

    def test_finish_logging_session_expired_as_warning(self):
        """SESSION_EXPIRED must log via Logger.warning with clean ASCII hyphen separator."""
        from services.accounts.results import SwitchResult
        result = SwitchResult(
            SwitchOutcome.SESSION_EXPIRED,
            SwitchPhase.VERIFYING,
            0,
            "smurf",
            "The Riot Client did not accept the saved session. Sign in once by hand to refresh it.",
        )
        with patch("utils.logger.Logger.warning") as mock_warn, patch("utils.logger.Logger.error") as mock_err:
            out = self.switcher._finish(result)
            self.assertEqual(out, result)
            mock_warn.assert_called_once()
            mock_err.assert_not_called()
            args, _ = mock_warn.call_args
            self.assertIn("switch failed for smurf: SESSION_EXPIRED - The Riot Client did not accept", args[1])
            self.assertNotIn("â€”", args[1])
            self.assertNotIn("—", args[1])

    def test_finish_logging_error_as_error(self):
        """Unexpected ERROR outcomes must log via Logger.error."""
        from services.accounts.results import SwitchResult
        result = SwitchResult(
            SwitchOutcome.ERROR,
            SwitchPhase.SIGNING_OUT,
            0,
            "main",
            "Hardware connection failure",
        )
        with patch("utils.logger.Logger.warning") as mock_warn, patch("utils.logger.Logger.error") as mock_err:
            out = self.switcher._finish(result)
            self.assertEqual(out, result)
            mock_err.assert_called_once()
            mock_warn.assert_not_called()
            args, _ = mock_err.call_args
            self.assertIn("switch failed for main: ERROR - Hardware connection failure", args[1])


if __name__ == "__main__":
    unittest.main()

