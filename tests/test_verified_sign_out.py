"""
Sign-out must be *verified*, the way a person sees it, before anything is typed.

Seen live (Oct 2026): "Sign out failed: no response", then the switch carried
on as if signed out - `is_signed_in()` read an unanswered session request as
"nobody signed in". The old session survived, and League later could not log
in. These tests pin the person-like flow down: close League (and wait until
it is gone), the Riot Client's own sign-out, then a positive "no session, no
authorization" from the client before the sign-in form is touched.
"""
import unittest
from unittest.mock import MagicMock

from services.accounts import RiotSession, SwitchOutcome
from tests.test_account_switching import FakeApi, Harness


class StrictApi(FakeApi):
    """FakeApi plus the read-backs the real RiotClientAPI has."""

    def __init__(self, *a, session_reads=None, auth_reads=None, **kw):
        super().__init__(*a, **kw)
        self.session_reads = list(session_reads or [])  # forced answers, in order
        self.auth_reads = list(auth_reads or [])

    def signed_out_state(self):
        if self.session_reads:
            return self.session_reads.pop(0)
        return self.signed_in_as is None

    def authorization_present(self):
        if self.auth_reads:
            return self.auth_reads.pop(0)
        return self.signed_in_as is not None


class VerifiedSignOutTests(unittest.TestCase):
    def test_unanswered_sign_out_is_a_failure_and_nothing_is_typed(self):
        api = StrictApi(signed_in_as="main_user", sign_out_works=False,
                        session_reads=[None] * 500)
        api.is_signed_in = lambda: False  # the old check: "no answer" == signed out
        h = Harness(api)
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.SIGN_OUT_FAILED)
        self.assertEqual(h.form.typed, [])
        self.assertEqual(api.calls.count("sign_out"), 2)  # one retry, then honest failure

    def test_types_only_after_the_client_confirms_the_sign_out(self):
        # Session still reads as authenticated twice after the DELETE.
        api = StrictApi(signed_in_as="main_user", session_reads=[False, False, False])
        h = Harness(api)
        h.switcher._sign_out_timeout_s = 0.5
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.SUCCESS, r)
        self.assertEqual(h.form.events[0], ("signed_in_while_typing", None))
        self.assertEqual(len(h.form.typed), 1)

    def test_a_leftover_authorization_means_not_signed_out(self):
        api = StrictApi(signed_in_as=None, auth_reads=[True] * 500)
        self.assertFalse(RiotSession(api).signed_out_confirmed())

    def test_league_is_closed_and_gone_before_the_sign_out_request(self):
        api = StrictApi(signed_in_as="main_user")
        h = Harness(api)
        league = {"running": True}
        order = []
        h.switcher._league_running = lambda: league["running"]
        def kill():
            order.append("kill")
            league["running"] = False
            return True
        h.switcher._kill_games = kill
        real_sign_out = api.sign_out
        def sign_out():
            order.append("sign_out:league_running=%s" % league["running"])
            return real_sign_out()
        api.sign_out = sign_out
        h.switcher.switch_to(1, launch_league=False)
        self.assertEqual(order[:2], ["kill", "sign_out:league_running=False"])

    def test_sign_in_screen_is_not_trusted_while_sign_out_is_unknown(self):
        api = StrictApi(signed_in_as=None, session_reads=[None] * 500)
        h = Harness(api)
        self.assertFalse(h.switcher._wait_for_sign_in_screen())

    def test_session_without_read_backs_falls_back_to_is_signed_in(self):
        self.assertTrue(RiotSession(FakeApi(signed_in_as=None)).signed_out_confirmed())
        self.assertFalse(RiotSession(FakeApi(signed_in_as="x")).signed_out_confirmed())

    def test_read_back_errors_are_not_signed_out(self):
        api = StrictApi()
        api.signed_out_state = MagicMock(side_effect=OSError("refused"))
        self.assertFalse(RiotSession(api).signed_out_confirmed())


class RiotClientApiReadBackTests(unittest.TestCase):
    def _api(self, res):
        from services.account_manager import RiotClientAPI
        api = RiotClientAPI()
        api.request = MagicMock(return_value=res)
        return api

    def _res(self, status, body=None):
        res = MagicMock(status_code=status)
        res.json.return_value = body
        return res

    def test_signed_out_state_mapping(self):
        self.assertIsNone(self._api(None).signed_out_state())
        self.assertTrue(self._api(self._res(404)).signed_out_state())
        self.assertFalse(self._api(self._res(200, {"type": "authenticated"})).signed_out_state())
        self.assertTrue(self._api(self._res(200, {"type": "unauthenticated"})).signed_out_state())
        self.assertIsNone(self._api(self._res(200, {})).signed_out_state())
        self.assertIsNone(self._api(self._res(500, {})).signed_out_state())

    def test_authorization_present_mapping(self):
        self.assertIsNone(self._api(None).authorization_present())
        self.assertTrue(self._api(self._res(200, {})).authorization_present())
        self.assertFalse(self._api(self._res(404)).authorization_present())

    def test_sign_out_is_the_clients_own_delete_sent_once_with_time(self):
        api = self._api(self._res(204))
        self.assertTrue(api.sign_out())
        args, kwargs = api.request.call_args
        self.assertEqual(args[:2], ("DELETE", "/rso-auth/v1/session"))
        self.assertEqual(kwargs.get("max_attempts"), 1)
        self.assertGreaterEqual(kwargs.get("timeout"), 10.0)

    def test_a_refused_sign_out_is_logged_as_refused_not_as_no_response(self):
        import requests
        from unittest.mock import patch
        res = requests.Response()
        res.status_code = 400
        res._content = b'{"errorCode":"sign_out_failed_other_games_running"}'
        api = self._api(res)
        with patch("services.account_manager.Logger") as log:
            self.assertFalse(api.sign_out())
        text = " ".join(str(c) for c in log.warning.call_args_list)
        self.assertIn("400", text)
        self.assertIn("other_games_running", text)
        self.assertNotIn("no response", text)


if __name__ == "__main__":
    unittest.main()
