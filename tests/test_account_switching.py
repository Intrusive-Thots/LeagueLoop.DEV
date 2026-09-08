"""
Account switching, driven against a fake Riot Client and a fake session vault.

The switch is no longer "sign out, then send the password": Riot's credential
sign-in carries an hCaptcha challenge, so that request is refused with
`invalid_prompt`. A switch is now a file operation — stop the client, swap the
saved session files, start it again — and these tests cover the branches that
sequence can take.

The properties worth protecting, and the failure each one prevents:

* a switch that cannot succeed must not close your running client to find out
* switching away must not lose the account you left
* the client must be *observed* gone before the files are swapped, because a
  swap underneath a live client is silently undone
* a restored-but-rejected session must not be reported as success
"""
import os
import shutil
import tempfile
import time
import unittest

from services.accounts import AccountSwitcher, RiotSession, SwitchOutcome, SwitchPhase
from services.accounts.results import NEEDS_MANUAL_SIGN_IN, OUTCOME_MESSAGES, RETRYABLE
from services.accounts.vault import SESSION_FILE, SessionVault


class FakeApi:
    """Stands in for RiotClientAPI."""

    def __init__(self, running=True, signed_in_as=None, sign_out_works=True,
                 connectable=True, accepts_session=True):
        self.running = running
        self.signed_in_as = signed_in_as
        self.sign_out_works = sign_out_works
        self.connectable = connectable
        self.is_connected = connectable
        #: Whether a restored session is honoured when the client restarts.
        #: False models an expired session: the client comes up logged out.
        self.accepts_session = accepts_session
        self.pending_account = None
        self.calls = []

    def is_riot_client_running(self):
        return self.running

    def connect(self):
        self.is_connected = self.connectable
        return self.connectable

    def is_signed_in(self):
        return self.signed_in_as is not None

    def get_current_user(self):
        if self.signed_in_as is None:
            return None
        return {"preferred_username": self.signed_in_as}

    def sign_out(self):
        self.calls.append(("sign_out", None))
        if self.sign_out_works:
            self.signed_in_as = None
        return self.sign_out_works


ACCOUNTS = [
    {"label": "Main", "username": "main_user"},
    {"label": "Smurf", "username": "smurf_user"},
]


class Harness:
    """A switcher wired to a fake client and a real vault on a temp directory."""

    def __init__(self, api, accounts=None, saved=(), can_observe_client=True,
                 client_stops=True):
        self.api = api
        self.tmp = tempfile.mkdtemp()
        self.live = os.path.join(self.tmp, "riot-data")
        os.makedirs(self.live)
        self.vault = SessionVault(os.path.join(self.tmp, "app"), data_dir=self.live)
        self.state = {
            "active": None, "signed_out": 0, "killed": 0,
            "stopped": 0, "launched": 0, "launched_league": None,
        }
        self._client_stops = client_stops

        if api.signed_in_as:
            self.write_live_session(api.signed_in_as)
        for name in saved:
            self.write_live_session(name)
            self.vault.capture(name)
        if api.signed_in_as:
            self.write_live_session(api.signed_in_as)
        elif saved:
            self._clear_live()

        self.switcher = AccountSwitcher(
            session=RiotSession(api),
            accounts_provider=lambda: accounts if accounts is not None else ACCOUNTS,
            vault=self.vault,
            on_success=self._on_success,
            on_signed_out=self._on_signed_out,
            kill_games=self._kill,
            stop_client=self._stop,
            client_running=(self._running if can_observe_client else None),
            launch_client=self._launch,
            sign_out_timeout_s=0.05,
            client_timeout_s=0.2,
            shutdown_timeout_s=0.3,
            settle_s=0.0,
        )

    # -- fake machine ----------------------------------------------------
    def write_live_session(self, name):
        with open(os.path.join(self.live, SESSION_FILE), "w", encoding="utf-8") as f:
            f.write("ssid: %s\n" % name)

    def _clear_live(self):
        path = os.path.join(self.live, SESSION_FILE)
        if os.path.exists(path):
            os.remove(path)

    def live_owner(self):
        path = os.path.join(self.live, SESSION_FILE)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return f.read().strip().split(": ")[1]

    def _on_success(self, i):
        self.state["active"] = i

    def _on_signed_out(self):
        self.state["signed_out"] += 1

    def _kill(self):
        self.state["killed"] += 1
        return True

    def _stop(self):
        self.state["stopped"] += 1
        if self._client_stops:
            self.api.running = False
            self.api.signed_in_as = None
        return True

    def _running(self):
        return self.api.running

    def _launch(self, league=True):
        self.state["launched"] += 1
        self.state["launched_league"] = league
        self.api.running = True
        # The client comes back up as whoever the restored session names —
        # unless that session is no longer accepted.
        if self.api.accepts_session:
            self.api.signed_in_as = self.live_owner()

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class SwitchSequenceTests(unittest.TestCase):
    def tearDown(self):
        harness = getattr(self, "h", None)
        if harness:
            harness.close()

    def test_a_saved_session_is_restored_and_the_client_restarted(self):
        self.h = Harness(FakeApi(signed_in_as="main_user"), saved=["smurf_user"])
        result = self.h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.SUCCESS)
        self.assertEqual(self.h.live_owner(), "smurf_user")
        self.assertEqual(self.h.state["active"], 1)
        self.assertEqual(self.h.state["launched"], 1)

    def test_no_password_is_ever_asked_for_or_sent(self):
        """Riot refuses a credential sign-in without a solved captcha, so a
        password is not merely unnecessary here — it cannot work. The switcher
        must not take one, hold one, or call anything that sends one."""
        import inspect
        import re

        signature = inspect.signature(AccountSwitcher.__init__)
        self.assertNotIn("password_provider", signature.parameters)
        for name in signature.parameters:
            self.assertNotIn("password", name.lower())

        source = inspect.getsource(AccountSwitcher)
        code = "\n".join(
            line for line in source.split("\n")
            if not line.strip().startswith("#")
        )
        self.assertIsNone(
            re.search(r"\.sign_in\s*\(", code),
            "the switcher still calls a credential sign-in",
        )
        self.assertIsNone(
            re.search(r"self\._password", code),
            "the switcher still holds a password provider",
        )

    def test_an_account_with_no_saved_session_fails_before_closing_anything(self):
        """A switch that cannot succeed must not take your client down first."""
        self.h = Harness(FakeApi(signed_in_as="main_user"))
        result = self.h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.NO_SAVED_SESSION)
        self.assertIs(result.phase, SwitchPhase.PREPARING)
        self.assertEqual(self.h.state["stopped"], 0)
        self.assertEqual(self.h.state["killed"], 0)
        self.assertTrue(self.h.api.running)

    def test_an_expired_session_fails_before_closing_anything(self):
        self.h = Harness(FakeApi(signed_in_as="main_user"), saved=["smurf_user"])
        slot = self.h.vault._slot("smurf_user")
        os.remove(os.path.join(slot, "session.json"))
        ancient = time.time() - 60 * 86400
        os.utime(os.path.join(slot, SESSION_FILE), (ancient, ancient))

        result = self.h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.SESSION_EXPIRED)
        self.assertEqual(self.h.state["stopped"], 0)

    def test_switching_away_keeps_the_account_being_left(self):
        """A → B → A must not need a manual sign-in for A."""
        self.h = Harness(FakeApi(signed_in_as="main_user"), saved=["smurf_user"])
        self.assertFalse(self.h.vault.info("main_user").exists)

        self.h.switcher.switch_to(1)
        self.assertTrue(
            self.h.vault.info("main_user").exists,
            "the outgoing account's session was lost",
        )

        result = self.h.switcher.switch_to(0)
        self.assertIs(result.outcome, SwitchOutcome.SUCCESS)
        self.assertEqual(self.h.live_owner(), "main_user")

    def test_already_active_is_a_no_op(self):
        self.h = Harness(FakeApi(signed_in_as="main_user"), saved=["main_user"])
        result = self.h.switcher.switch_to(0)
        self.assertIs(result.outcome, SwitchOutcome.ALREADY_ACTIVE)
        self.assertEqual(self.h.state["stopped"], 0)
        self.assertEqual(self.h.state["active"], 0)

    def test_a_client_that_will_not_close_stops_the_switch(self):
        """Swapping the files underneath a live client is silently undone."""
        self.h = Harness(
            FakeApi(signed_in_as="main_user"), saved=["smurf_user"],
            client_stops=False,
        )
        result = self.h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.CLIENT_STILL_RUNNING)
        self.assertIs(result.phase, SwitchPhase.CLOSING_CLIENT)
        self.assertEqual(self.h.live_owner(), "main_user", "the session was swapped anyway")

    def test_a_rejected_session_is_reported_as_expired_not_success(self):
        """The client comes back up on a login screen. Calling that success is
        the most misleading thing this sequence could do."""
        self.h = Harness(
            FakeApi(signed_in_as="main_user", accepts_session=False),
            saved=["smurf_user"],
        )
        result = self.h.switcher.switch_to(1)
        self.assertIs(result.outcome, SwitchOutcome.SESSION_EXPIRED)
        self.assertIs(result.phase, SwitchPhase.VERIFYING)
        self.assertIsNone(self.h.state["active"])

    def test_a_successful_switch_recaptures_and_resets_the_clock(self):
        """The client rewrites the session on sign-in, so what is on disk is
        fresher than what we restored. Re-capturing is why regular use keeps a
        session alive."""
        self.h = Harness(FakeApi(signed_in_as="main_user"), saved=["smurf_user"])
        slot = self.h.vault._slot("smurf_user")
        os.utime(os.path.join(slot, SESSION_FILE), (1000, 1000))
        before = self.h.vault.info("smurf_user").captured_at

        self.h.switcher.switch_to(1)
        self.assertGreater(self.h.vault.info("smurf_user").captured_at, before)

    def test_an_invalid_index_is_rejected(self):
        self.h = Harness(FakeApi(signed_in_as="main_user"))
        self.assertIs(
            self.h.switcher.switch_to(9).outcome, SwitchOutcome.INVALID_ACCOUNT
        )

    def test_league_is_launched_only_when_asked(self):
        self.h = Harness(FakeApi(signed_in_as="main_user"), saved=["smurf_user"])
        self.h.switcher.switch_to(1, launch_league=False)
        self.assertIs(self.h.state["launched_league"], False)

    def test_a_session_is_filed_under_the_username_not_the_label(self):
        """Renaming the display label must not orphan the saved session."""
        self.assertEqual(
            AccountSwitcher.account_key({"label": "Main", "username": "Main_User"}),
            "main_user",
        )
        self.assertEqual(
            AccountSwitcher.account_key({"label": "Only A Label"}), "only a label"
        )


class CaptureTests(unittest.TestCase):
    def tearDown(self):
        self.h.close()

    def test_capturing_after_a_manual_sign_in_is_the_way_sessions_appear(self):
        self.h = Harness(FakeApi(signed_in_as="main_user"))
        self.h.write_live_session("main_user")
        self.assertTrue(self.h.switcher.capture_current(0))
        self.assertTrue(self.h.vault.info("main_user").exists)

    def test_session_info_is_offered_per_account_row(self):
        self.h = Harness(FakeApi(signed_in_as="main_user"), saved=["main_user"])
        info = self.h.switcher.session_info(0)
        self.assertTrue(info.exists)
        self.assertIn("session", info.describe().lower())
        self.assertIsNone(self.h.switcher.session_info(9))


class SignOutTests(unittest.TestCase):
    def tearDown(self):
        self.h.close()

    def test_sign_out_closes_league_first(self):
        """The Riot Client refuses sign-out with other games running."""
        self.h = Harness(FakeApi(signed_in_as="main_user"))
        result = self.h.switcher.sign_out()
        self.assertIs(result.outcome, SwitchOutcome.SUCCESS)
        self.assertEqual(self.h.state["killed"], 1)
        self.assertEqual(self.h.state["signed_out"], 1)

    def test_sign_out_keeps_the_session_it_is_signing_out_of(self):
        """Otherwise signing out silently costs the ability to switch back."""
        self.h = Harness(FakeApi(signed_in_as="main_user"))
        self.h.write_live_session("main_user")
        self.h.switcher.sign_out()
        self.assertTrue(self.h.vault.info("main_user").exists)

    def test_sign_out_when_nobody_is_signed_in_is_success(self):
        self.h = Harness(FakeApi(signed_in_as=None))
        self.assertIs(self.h.switcher.sign_out().outcome, SwitchOutcome.SUCCESS)

    def test_a_refused_sign_out_is_reported(self):
        self.h = Harness(FakeApi(signed_in_as="main_user", sign_out_works=False))
        result = self.h.switcher.sign_out()
        self.assertIs(result.outcome, SwitchOutcome.SIGN_OUT_FAILED)


class OutcomeVocabularyTests(unittest.TestCase):
    def test_every_outcome_has_a_sentence(self):
        for outcome in SwitchOutcome:
            self.assertIn(outcome, OUTCOME_MESSAGES, outcome)
            self.assertTrue(OUTCOME_MESSAGES[outcome].strip())

    def test_the_session_outcomes_tell_the_user_to_sign_in_by_hand(self):
        for outcome in NEEDS_MANUAL_SIGN_IN:
            self.assertIn("hand", OUTCOME_MESSAGES[outcome].lower(), outcome)

    def test_an_unclearable_outcome_is_not_also_offered_as_retryable(self):
        """Retrying these is a spinner that never ends."""
        self.assertEqual(NEEDS_MANUAL_SIGN_IN & RETRYABLE, frozenset())


class ConcurrencyTests(unittest.TestCase):
    def tearDown(self):
        self.h.close()

    def test_one_lock_covers_switch_and_sign_out(self):
        """The old code had a login-only flag that sign_out ignored, so you
        could sign out halfway through a login."""
        import threading

        self.h = Harness(FakeApi(signed_in_as="main_user"), saved=["smurf_user"])
        started, release = threading.Event(), threading.Event()
        outcomes = []

        original = self.h.vault.restore

        def slow_restore(key):
            started.set()
            release.wait(2.0)
            return original(key)

        self.h.vault.restore = slow_restore
        worker = threading.Thread(
            target=lambda: outcomes.append(self.h.switcher.switch_to(1))
        )
        worker.start()
        started.wait(2.0)
        try:
            self.assertIs(self.h.switcher.sign_out().outcome, SwitchOutcome.BUSY)
        finally:
            release.set()
            worker.join(5.0)


class EventTests(unittest.TestCase):
    def tearDown(self):
        self.h.close()

    def test_every_phase_of_a_switch_is_announced(self):
        seen = []

        class Bus:
            def emit(self, channel, payload):
                seen.append((channel, getattr(payload, "phase", None)))

        self.h = Harness(FakeApi(signed_in_as="main_user"), saved=["smurf_user"])
        self.h.switcher._bus = Bus()
        self.h.switcher.switch_to(1)

        phases = [phase for _, phase in seen if phase]
        for expected in (
            SwitchPhase.CAPTURING, SwitchPhase.CLOSING_CLIENT,
            SwitchPhase.RESTORING_SESSION, SwitchPhase.LAUNCHING,
            SwitchPhase.VERIFYING,
        ):
            self.assertIn(expected, phases, expected)

    def test_a_finished_event_is_emitted_even_when_the_switch_fails(self):
        """Without it the UI sits disabled forever."""
        from services.accounts.results import EVENT_SWITCH_FINISHED

        channels = []

        class Bus:
            def emit(self, channel, payload):
                channels.append(channel)

        self.h = Harness(FakeApi(signed_in_as="main_user"))
        self.h.switcher._bus = Bus()
        self.h.switcher.switch_to(1)
        self.assertIn(EVENT_SWITCH_FINISHED, channels)


if __name__ == "__main__":
    unittest.main()
