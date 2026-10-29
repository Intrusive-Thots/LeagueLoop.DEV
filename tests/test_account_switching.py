"""
Account switching, driven against a fake Riot Client and a fake sign-in form.

The switch is: sign the current account out, wait for the Riot sign-in form,
type the stored username + password into it, submit, and wait for Riot to
confirm. (Restoring saved session files was tried and does not work: without
"Stay signed in" the client keeps no reusable session - every restore landed
on the sign-in screen.)

Properties protected here, and the failure each one prevents:

* a switch that cannot work (no password) does not sign you out first
* the current account is signed out *before* anything is typed
* nothing is typed before the sign-in window is there
* a submitted form is not reported as success until Riot says so
* 2FA, captcha, wrong password and rate limiting are reported as such
* the password never appears in a progress message, result or log line
"""
import threading
import unittest
from unittest.mock import patch

from services.accounts import AccountSwitcher, RiotSession, SwitchOutcome, SwitchPhase
from services.accounts.form_login import FillResult, FillStatus
from services.accounts.results import NEEDS_MANUAL_SIGN_IN, OUTCOME_MESSAGES, RETRYABLE

SECRET = "hunter2-S3cr3t!"


class FakeApi:
    """Stands in for RiotClientAPI."""

    def __init__(self, running=True, signed_in_as=None, sign_out_works=True,
                 connectable=True):
        self.running = running
        self.signed_in_as = signed_in_as
        self.sign_out_works = sign_out_works
        self.connectable = connectable
        self.is_connected = connectable
        self.auth = None
        self.calls = []

    def is_riot_client_running(self):
        return self.running

    def connect(self):
        self.is_connected = self.connectable and self.running
        return self.is_connected

    def is_signed_in(self):
        return self.signed_in_as is not None

    def get_current_user(self):
        if self.signed_in_as is None:
            return None
        return {"preferred_username": self.signed_in_as}

    def get_authenticator_state(self):
        return self.auth

    def sign_out(self):
        self.calls.append("sign_out")
        if self.sign_out_works:
            self.signed_in_as = None
        return self.sign_out_works

    def launch_league_of_legends(self):
        self.calls.append("launch_league")
        return True


class FakeForm:
    """Stands in for RiotFormFiller. `riot` decides what Riot does on submit."""

    def __init__(self, api, riot="accept", window=True, status=FillStatus.SUBMITTED):
        self.api = api
        self.riot = riot
        self.window = window
        self.status = status
        self.typed = []
        self.events = []

    def available(self):
        return True

    def wait_for_window(self, timeout_s=None):
        return 7 if self.window else 0

    def form_ready(self, hwnd):
        return None

    def captcha_visible(self):
        return True if self.riot == "captcha" else None

    def fill_and_submit(self, username, password, on_step=None):
        # The ordering guarantee: nobody is signed in while we type.
        self.events.append(("signed_in_while_typing", self.api.signed_in_as))
        self.typed.append((username, password))
        if self.status is not FillStatus.SUBMITTED:
            return FillResult(self.status, 3)
        if self.riot == "accept":
            self.api.signed_in_as = username.lower()
        elif self.riot == "other":
            self.api.signed_in_as = "someone_else"
        elif self.riot == "bad_password":
            self.api.auth = {"type": "auth", "error": "auth_failure"}
        elif self.riot == "rate_limited":
            self.api.auth = {"type": "auth", "error": "rate_limited"}
        elif self.riot == "2fa":
            self.api.auth = {"type": "multifactor", "multifactor": {"method": "email"}}
        return FillResult(FillStatus.SUBMITTED, 1)


ACCOUNTS = [
    {"label": "Main", "username": "main_user"},
    {"label": "Smurf", "username": "Smurf_User"},
    {"label": "NoPw", "username": "nopw_user"},
]
PASSWORDS = {0: "main-pw", 1: SECRET, 2: ""}


class Harness:
    def __init__(self, api, riot="accept", window=True, status=FillStatus.SUBMITTED,
                 verify_timeout_s=0.3):
        self.api = api
        self.form = FakeForm(api, riot, window, status)
        self.state = {"active": None, "signed_out": 0, "killed": 0, "launched": []}
        self.progress = []
        harness = self

        class Bus:
            def emit(self, channel, payload):
                harness.progress.append((channel, payload))

        self.switcher = AccountSwitcher(
            session=RiotSession(api),
            accounts_provider=lambda: ACCOUNTS,
            password_provider=lambda i: PASSWORDS.get(i, ""),
            form_filler=self.form,
            on_success=self._on_success,
            on_signed_out=self._on_signed_out,
            kill_games=self._kill,
            client_running=lambda: api.running,
            launch_client=self._launch,
            bus=Bus(),
            sign_out_timeout_s=0.05,
            client_timeout_s=0.2,
            sign_in_screen_timeout_s=0.2,
            verify_timeout_s=verify_timeout_s,
            nudge_after_s=0.05,
            reopen_after_s=0.05,
            poll_s=0.01,
        )

    def _on_success(self, i):
        self.state["active"] = i

    def _on_signed_out(self):
        self.state["signed_out"] += 1

    def _kill(self):
        self.state["killed"] += 1
        return True

    def _launch(self, league=True):
        self.state["launched"].append(league)
        self.api.running = True

    def messages(self):
        return [getattr(p, "message", "") for _, p in self.progress]

    def phases(self):
        return [getattr(p, "phase", None) for _, p in self.progress]


class SwitchSequenceTests(unittest.TestCase):
    def test_signs_out_then_types_the_target_credentials_then_launches_league(self):
        h = Harness(FakeApi(signed_in_as="main_user"))
        result = h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.SUCCESS, result)
        self.assertEqual(h.form.typed, [("Smurf_User", SECRET)])
        self.assertEqual(h.form.events, [("signed_in_while_typing", None)])
        self.assertEqual(h.api.calls, ["sign_out", "launch_league"])
        self.assertEqual(h.state["active"], 1)
        self.assertGreaterEqual(h.state["killed"], 1)  # League closed before sign-out

    def test_every_step_is_announced_in_order(self):
        h = Harness(FakeApi(signed_in_as="main_user"))
        h.switcher.switch_to(1)
        phases = [p for p in h.phases() if p]
        order = [SwitchPhase.SIGNING_OUT, SwitchPhase.WAITING_FOR_SIGN_IN,
                 SwitchPhase.FILLING_FORM, SwitchPhase.VERIFYING, SwitchPhase.LAUNCHING]
        positions = [phases.index(p) for p in order]
        self.assertEqual(positions, sorted(positions), phases)
        joined = " | ".join(h.messages())
        self.assertIn("Signing out main_user", joined)
        self.assertIn("Waiting for the Riot sign-in screen", joined)
        self.assertIn("don't click other windows", joined)

    def test_no_password_means_nothing_is_signed_out(self):
        h = Harness(FakeApi(signed_in_as="main_user"))
        result = h.switcher.switch_to(2)
        self.assertIs(result.outcome, SwitchOutcome.NO_CREDENTIALS)
        self.assertEqual(h.api.calls, [])
        self.assertEqual(h.api.signed_in_as, "main_user")
        self.assertIn("Edit", result.message)

    def test_already_active_is_a_no_op(self):
        h = Harness(FakeApi(signed_in_as="smurf_user"))
        result = h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.ALREADY_ACTIVE)
        self.assertNotIn("sign_out", h.api.calls)
        self.assertEqual(h.form.typed, [])

    def test_a_signed_out_client_goes_straight_to_the_form(self):
        h = Harness(FakeApi(signed_in_as=None))
        result = h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.SUCCESS)
        self.assertNotIn("sign_out", h.api.calls)

    def test_a_closed_riot_client_is_started_first(self):
        h = Harness(FakeApi(running=False))
        result = h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.SUCCESS, result)
        self.assertEqual(h.state["launched"][0], False)  # client only, not League yet

    def test_a_refused_sign_out_stops_before_typing(self):
        h = Harness(FakeApi(signed_in_as="main_user", sign_out_works=False))
        result = h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.SIGN_OUT_FAILED)
        self.assertEqual(h.form.typed, [])
        self.assertEqual(h.api.calls.count("sign_out"), 2)  # one retry

    def test_no_sign_in_window_stops_before_typing(self):
        h = Harness(FakeApi(signed_in_as="main_user"), window=False)
        result = h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.LOGIN_FORM_NOT_FOUND)
        self.assertEqual(h.form.typed, [])
        self.assertIn(False, h.state["launched"])  # asked the client to open once

    def test_focus_lost_on_every_attempt_is_reported(self):
        h = Harness(FakeApi(signed_in_as="main_user"), status=FillStatus.FOCUS_LOST)
        result = h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.FOCUS_LOST)
        self.assertIn("other windows", result.message)
        self.assertTrue(result.retryable)

    def test_wrong_password(self):
        h = Harness(FakeApi(signed_in_as="main_user"), riot="bad_password")
        self.assertIs(h.switcher.switch_to(1).outcome, SwitchOutcome.BAD_CREDENTIALS)

    def test_rate_limited(self):
        h = Harness(FakeApi(signed_in_as="main_user"), riot="rate_limited")
        self.assertIs(h.switcher.switch_to(1).outcome, SwitchOutcome.RATE_LIMITED)

    def test_two_factor_is_announced_and_waited_for(self):
        h = Harness(FakeApi(signed_in_as="main_user"), riot="2fa")
        result = h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.NEEDS_2FA)
        self.assertTrue(any("two-factor" in m for m in h.messages()))

    def test_two_factor_entered_by_the_user_finishes_the_switch(self):
        api = FakeApi(signed_in_as="main_user")
        h = Harness(api, riot="2fa", verify_timeout_s=2.0)
        timer = threading.Timer(0.15, lambda: setattr(api, "signed_in_as", "smurf_user"))
        timer.start()
        try:
            self.assertIs(h.switcher.switch_to(1).outcome, SwitchOutcome.SUCCESS)
        finally:
            timer.cancel()

    def test_captcha_is_announced_and_reported(self):
        h = Harness(FakeApi(signed_in_as="main_user"), riot="captcha")
        result = h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.CAPTCHA_REQUIRED)
        self.assertTrue(any("captcha" in m.lower() for m in h.messages()))
        self.assertIn("captcha", result.message.lower())

    def test_captcha_from_the_authenticator_state_is_recognised(self):
        api = FakeApi(signed_in_as="main_user")
        h = Harness(api, riot="silent")
        original = h.form.fill_and_submit

        def submit(u, p, on_step=None):
            r = original(u, p, on_step)
            api.auth = {"type": "auth", "error": "invalid_prompt"}
            return r

        h.form.fill_and_submit = submit
        self.assertIs(h.switcher.switch_to(1).outcome, SwitchOutcome.CAPTCHA_REQUIRED)

    def test_a_stale_error_from_before_the_attempt_is_ignored(self):
        api = FakeApi(signed_in_as="main_user")
        api.auth = {"type": "auth", "error": "auth_failure"}
        h = Harness(api, riot="accept")
        self.assertIs(h.switcher.switch_to(1).outcome, SwitchOutcome.SUCCESS)

    def test_silence_nudges_then_times_out(self):
        h = Harness(FakeApi(signed_in_as="main_user"), riot="silent")
        result = h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.TIMED_OUT)
        self.assertTrue(any("Still waiting for Riot" in m for m in h.messages()))
        self.assertIsNot(h.state["active"], 1)

    def test_signed_in_as_someone_else_is_not_success(self):
        h = Harness(FakeApi(signed_in_as="main_user"), riot="other")
        self.assertIs(h.switcher.switch_to(1).outcome, SwitchOutcome.WRONG_ACCOUNT)

    def test_league_is_launched_only_when_asked(self):
        h = Harness(FakeApi(signed_in_as="main_user"))
        h.switcher.switch_to(1, launch_league=False)
        self.assertNotIn("launch_league", h.api.calls)

    def test_an_invalid_index_is_rejected(self):
        h = Harness(FakeApi())
        self.assertIs(h.switcher.switch_to(9).outcome, SwitchOutcome.INVALID_ACCOUNT)


class PasswordHygieneTests(unittest.TestCase):
    def test_the_password_is_never_in_messages_results_or_logs(self):
        logged = []

        def grab(*args, **kwargs):
            logged.append(" ".join(str(a) for a in args) + " " + " ".join(
                "%s=%s" % kv for kv in kwargs.items()))

        for riot in ("accept", "bad_password", "silent", "captcha", "2fa"):
            with patch("utils.logger.Logger.info", side_effect=grab), \
                 patch("utils.logger.Logger.warning", side_effect=grab), \
                 patch("utils.logger.Logger.error", side_effect=grab), \
                 patch("utils.logger.Logger.debug", side_effect=grab), \
                 patch("utils.logger.Logger.action", side_effect=grab):
                h = Harness(FakeApi(signed_in_as="main_user"), riot=riot, verify_timeout_s=0.1)
                result = h.switcher.switch_to(1)
            blob = " ".join(logged) + " ".join(h.messages()) + str(result) + result.detail
            self.assertNotIn(SECRET, blob, riot)

    def test_a_crash_while_typing_does_not_echo_the_exception_text(self):
        h = Harness(FakeApi(signed_in_as="main_user"))

        def boom(u, p, on_step=None):
            raise RuntimeError("typed " + p)

        h.form.fill_and_submit = boom
        result = h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.ERROR)
        self.assertNotIn(SECRET, str(result) + result.detail)


class SignOutTests(unittest.TestCase):
    def test_sign_out_closes_league_first(self):
        h = Harness(FakeApi(signed_in_as="main_user"))
        self.assertIs(h.switcher.sign_out().outcome, SwitchOutcome.SUCCESS)
        self.assertEqual(h.state["killed"], 1)
        self.assertEqual(h.state["signed_out"], 1)

    def test_sign_out_when_nobody_is_signed_in_is_success(self):
        h = Harness(FakeApi(signed_in_as=None))
        self.assertIs(h.switcher.sign_out().outcome, SwitchOutcome.SUCCESS)

    def test_a_refused_sign_out_is_reported(self):
        h = Harness(FakeApi(signed_in_as="main_user", sign_out_works=False))
        self.assertIs(h.switcher.sign_out().outcome, SwitchOutcome.SIGN_OUT_FAILED)


class VocabularyTests(unittest.TestCase):
    def test_every_outcome_has_a_sentence(self):
        for outcome in SwitchOutcome:
            self.assertIn(outcome, OUTCOME_MESSAGES, outcome)
            self.assertTrue(OUTCOME_MESSAGES[outcome].strip())

    def test_outcomes_only_a_person_can_clear_say_by_hand(self):
        for outcome in NEEDS_MANUAL_SIGN_IN:
            self.assertIn("hand", OUTCOME_MESSAGES[outcome].lower(), outcome)

    def test_an_unclearable_outcome_is_not_also_offered_as_retryable(self):
        self.assertEqual(NEEDS_MANUAL_SIGN_IN & RETRYABLE, frozenset())

    def test_auth_state_classification(self):
        c = RiotSession.classify_auth_state
        self.assertEqual(c(None), "")
        self.assertEqual(c({"type": "success"}), "success")
        self.assertEqual(c({"type": "multifactor"}), "multifactor")
        self.assertEqual(c({"type": "auth", "error": "auth_failure"}), "auth_failure")
        self.assertEqual(c({"type": "auth", "error": {"errorCode": "rate_limited"}}), "rate_limited")
        self.assertEqual(c({"type": "auth", "error": "invalid_prompt"}), "captcha")
        self.assertEqual(c({"type": "auth", "error": "something_new"}), "")
        self.assertEqual(c("not a dict"), "")


class ConcurrencyTests(unittest.TestCase):
    def test_one_lock_covers_switch_and_sign_out(self):
        h = Harness(FakeApi(signed_in_as="main_user"))
        started, release = threading.Event(), threading.Event()
        original = h.form.fill_and_submit

        def slow(u, p, on_step=None):
            started.set()
            release.wait(2.0)
            return original(u, p, on_step)

        h.form.fill_and_submit = slow
        worker = threading.Thread(target=lambda: h.switcher.switch_to(1))
        worker.start()
        started.wait(2.0)
        try:
            self.assertIs(h.switcher.sign_out().outcome, SwitchOutcome.BUSY)
        finally:
            release.set()
            worker.join(5.0)

    def test_a_finished_event_is_emitted_even_when_the_switch_fails(self):
        from services.accounts.results import EVENT_SWITCH_FINISHED

        h = Harness(FakeApi(signed_in_as="main_user"), riot="bad_password")
        h.switcher.switch_to(1)
        self.assertIn(EVENT_SWITCH_FINISHED, [c for c, _ in h.progress])


if __name__ == "__main__":
    unittest.main()
