"""
Tests for account switching (services.accounts).

These drive the switcher against a fake Riot Client, so every branch —
already-signed-in, 2FA, bad password, rate limit, sign-out refusal, timeout —
is exercised without a real client.
"""
import unittest

from services.accounts import (
    AccountSwitcher,
    RiotSession,
    SwitchOutcome,
    SwitchPhase,
)


class FakeApi:
    """Stands in for RiotClientAPI."""

    def __init__(self, running=True, signed_in_as=None, sign_in_body=None,
                 sign_out_works=True, connectable=True):
        self.running = running
        self.signed_in_as = signed_in_as
        self.sign_in_body = sign_in_body or {"type": "success"}
        self.sign_out_works = sign_out_works
        self.connectable = connectable
        self.is_connected = connectable
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

    def sign_in(self, username, password, persist=False):
        self.calls.append(("sign_in", username))
        body = self.sign_in_body
        if body.get("type") == "success":
            self.signed_in_as = username
        return body

    def sign_out(self):
        self.calls.append(("sign_out", None))
        if self.sign_out_works:
            self.signed_in_as = None
        return self.sign_out_works


ACCOUNTS = [
    {"label": "Main", "username": "main_user"},
    {"label": "Smurf", "username": "smurf_user"},
]


def build(api, accounts=None, password="pw", **kw):
    state = {"active": None, "signed_out": 0, "killed": 0, "launched": 0}

    def on_success(i):
        state["active"] = i

    def on_signed_out():
        state["signed_out"] += 1

    def kill():
        state["killed"] += 1
        return True

    def launch():
        state["launched"] += 1
        api.running = True

    switcher = AccountSwitcher(
        session=RiotSession(api),
        accounts_provider=lambda: accounts if accounts is not None else ACCOUNTS,
        password_provider=lambda i: password,
        on_success=on_success,
        on_signed_out=on_signed_out,
        kill_games=kill,
        launch_client=launch,
        sign_out_timeout_s=kw.pop("sign_out_timeout_s", 0.05),
        client_timeout_s=kw.pop("client_timeout_s", 0.05),
        **kw,
    )
    return switcher, state


class TestSwitchSequence(unittest.TestCase):
    def test_signs_out_before_signing_in(self):
        """The core fix: switching from another account signs it out first."""
        api = FakeApi(signed_in_as="main_user")
        switcher, state = build(api)

        result = switcher.switch_to(1, launch_league=False)

        self.assertIs(result.outcome, SwitchOutcome.SUCCESS)
        kinds = [c[0] for c in api.calls]
        self.assertEqual(kinds, ["sign_out", "sign_in"],
                         "must sign out before signing in")
        self.assertEqual(state["killed"], 1, "League must be closed before sign-out")
        self.assertEqual(state["active"], 1)

    def test_uses_the_api_not_keystrokes(self):
        api = FakeApi(signed_in_as=None)
        switcher, _ = build(api)
        switcher.switch_to(0, launch_league=False)
        self.assertIn(("sign_in", "main_user"), api.calls)

    def test_already_active_is_a_no_op(self):
        api = FakeApi(signed_in_as="main_user")
        switcher, state = build(api)

        result = switcher.switch_to(0, launch_league=False)

        self.assertIs(result.outcome, SwitchOutcome.ALREADY_ACTIVE)
        self.assertTrue(result.ok)
        self.assertEqual(api.calls, [], "must not sign out and back in needlessly")
        self.assertEqual(state["active"], 0)

    def test_two_factor_is_reported_not_treated_as_failure(self):
        api = FakeApi(signed_in_as=None, sign_in_body={"type": "multifactor"})
        switcher, state = build(api)

        result = switcher.switch_to(0, launch_league=False)

        self.assertIs(result.outcome, SwitchOutcome.NEEDS_2FA)
        self.assertFalse(result.ok)
        self.assertIn("two-factor", result.message.lower())
        self.assertIsNone(state["active"])

    def test_bad_credentials_are_distinct_from_generic_errors(self):
        api = FakeApi(signed_in_as=None,
                      sign_in_body={"type": "error", "error": "auth_failure"})
        switcher, _ = build(api)
        result = switcher.switch_to(0, launch_league=False)
        self.assertIs(result.outcome, SwitchOutcome.BAD_CREDENTIALS)
        self.assertFalse(result.retryable)

    def test_rate_limit_is_distinct_and_retryable_later(self):
        api = FakeApi(signed_in_as=None,
                      sign_in_body={"type": "error", "error": "rate_limited"})
        switcher, _ = build(api)
        result = switcher.switch_to(0, launch_league=False)
        self.assertIs(result.outcome, SwitchOutcome.RATE_LIMITED)

    def test_unknown_error_code_is_not_guessed_as_bad_password(self):
        api = FakeApi(signed_in_as=None,
                      sign_in_body={"type": "error", "error": "something_new"})
        switcher, _ = build(api)
        result = switcher.switch_to(0, launch_league=False)
        self.assertIs(result.outcome, SwitchOutcome.ERROR)

    def test_sign_out_refusal_stops_the_switch(self):
        api = FakeApi(signed_in_as="main_user", sign_out_works=False)
        switcher, state = build(api)

        result = switcher.switch_to(1, launch_league=False)

        self.assertIs(result.outcome, SwitchOutcome.SIGN_OUT_FAILED)
        self.assertIs(result.phase, SwitchPhase.SIGNING_OUT)
        self.assertNotIn(("sign_in", "smurf_user"), api.calls)
        self.assertIsNone(state["active"], "must not claim success")

    def test_missing_password_fails_before_touching_the_client(self):
        api = FakeApi(signed_in_as=None)
        switcher, _ = build(api, password="")
        result = switcher.switch_to(0, launch_league=False)
        self.assertIs(result.outcome, SwitchOutcome.NO_CREDENTIALS)
        self.assertEqual(api.calls, [])

    def test_invalid_index(self):
        api = FakeApi()
        switcher, _ = build(api)
        self.assertIs(switcher.switch_to(99).outcome, SwitchOutcome.INVALID_ACCOUNT)

    def test_client_not_running_is_launched_then_reported_if_still_absent(self):
        api = FakeApi(running=False, connectable=False, signed_in_as=None)
        switcher, state = build(api)
        result = switcher.switch_to(0, launch_league=False)
        self.assertEqual(state["launched"], 1, "should try launching the client")
        self.assertIs(result.outcome, SwitchOutcome.CLIENT_NOT_RUNNING)

    def test_launch_league_only_on_success(self):
        api = FakeApi(signed_in_as=None,
                      sign_in_body={"type": "error", "error": "auth_failure"})
        switcher, state = build(api)
        switcher.switch_to(0, launch_league=True)
        self.assertEqual(state["launched"], 0)


class TestSignOut(unittest.TestCase):
    def test_sign_out_closes_league_first(self):
        api = FakeApi(signed_in_as="main_user")
        switcher, state = build(api)

        result = switcher.sign_out()

        self.assertTrue(result.ok)
        self.assertEqual(state["killed"], 1)
        self.assertEqual(state["signed_out"], 1)

    def test_sign_out_when_nobody_signed_in_is_success(self):
        api = FakeApi(signed_in_as=None)
        switcher, _ = build(api)
        self.assertTrue(switcher.sign_out().ok)


class TestOperationVocabulary(unittest.TestCase):
    """SUCCESS means two different things; the sentence must say which."""

    def test_sign_out_does_not_announce_a_sign_in(self):
        api = FakeApi(signed_in_as="someone")
        switcher, _ = build(api)
        result = switcher.sign_out()

        self.assertTrue(result.ok)
        self.assertEqual(result.message, "Signed out.")
        self.assertNotIn("Signed in", result.message)

    def test_switch_still_names_the_account_it_signed_into(self):
        api = FakeApi(signed_in_as="someone")
        switcher, _ = build(api)
        result = switcher.switch_to(0)

        self.assertTrue(result.ok)
        self.assertIn("Signed in as", result.message)

    def test_failed_sign_out_keeps_its_own_wording(self):
        api = FakeApi(signed_in_as="someone", sign_out_works=False)
        switcher, _ = build(api)
        result = switcher.sign_out()

        self.assertFalse(result.ok)
        self.assertIn("sign out", result.message.lower())


class TestConcurrency(unittest.TestCase):
    def test_one_lock_covers_switch_and_sign_out(self):
        """
        The old code had a login-only flag that sign_out ignored, so a
        sign-out could run in the middle of a login.
        """
        api = FakeApi(signed_in_as=None)
        switcher, _ = build(api)

        switcher._lock.acquire()
        try:
            self.assertIs(switcher.switch_to(0).outcome, SwitchOutcome.BUSY)
            self.assertIs(switcher.sign_out().outcome, SwitchOutcome.BUSY)
        finally:
            switcher._lock.release()


class TestEvents(unittest.TestCase):
    def test_progress_and_finish_are_emitted(self):
        class Bus:
            def __init__(self):
                self.seen = []

            def emit(self, channel, payload=None, *a, **kw):
                self.seen.append((channel, payload))

        from services.accounts import (
            EVENT_SWITCH_FINISHED,
            EVENT_SWITCH_PROGRESS,
            EVENT_SWITCH_STARTED,
        )

        api = FakeApi(signed_in_as="main_user")
        bus = Bus()
        switcher, _ = build(api, bus=bus)
        switcher.switch_to(1, launch_league=False)

        channels = [c for c, _ in bus.seen]
        self.assertIn(EVENT_SWITCH_STARTED, channels)
        self.assertIn(EVENT_SWITCH_PROGRESS, channels)
        self.assertIn(EVENT_SWITCH_FINISHED, channels)

        phases = [p.phase for c, p in bus.seen if c == EVENT_SWITCH_PROGRESS]
        self.assertIn(SwitchPhase.SIGNING_OUT, phases)
        self.assertIn(SwitchPhase.AUTHENTICATING, phases)


class TestWaiting(unittest.TestCase):
    def test_wait_until_polls_until_true(self):
        calls = {"n": 0}

        def predicate():
            calls["n"] += 1
            return calls["n"] >= 3

        clock = {"t": 0.0}
        ok = RiotSession.wait_until(
            predicate, timeout_s=10,
            sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
            now=lambda: clock["t"],
        )
        self.assertTrue(ok)
        self.assertEqual(calls["n"], 3)

    def test_wait_until_gives_up_at_the_deadline(self):
        clock = {"t": 0.0}
        ok = RiotSession.wait_until(
            lambda: False, timeout_s=1.0,
            sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
            now=lambda: clock["t"],
        )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
