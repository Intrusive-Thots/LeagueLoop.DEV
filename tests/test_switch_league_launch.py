"""
After the sign-in: pressing Play, and making sure League is on the right account.

Seen live (Oct 2026): the launch request took 7-10 s and the old 3 s timeout
retried it; right after sign-in the Riot Client dropped the launch; and once
League came up logged in as the *previous* account while the Riot Client was
on the new one. Each test below pins one of those down.
"""
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from services.accounts import SwitchOutcome
from services.accounts.league_identity import league_login_puuid
from services.accounts.session import RiotSession
from tests.test_account_switching import FakeApi, Harness, SECRET


class IdApi(FakeApi):
    def get_auth_status(self):
        if self.signed_in_as is None:
            return None
        return {"subject": "PUUID-" + self.signed_in_as}


class LeagueWorld:
    """A fake League process plus whatever account it logs in as."""

    def __init__(self, h, start_on=("api",), login_as=None, api_block_s=0.0):
        self.h = h
        self.running = False
        self.start_on = set(start_on)
        self.login_as = list(login_as or [])  # one entry per League start
        self.api_block_s = api_block_s
        self.api_calls = 0
        self.exe_calls = 0
        self.current_login = None
        sw = h.switcher
        sw._league_running = lambda: self.running
        sw._launch_league_exe = self._exe
        sw._league_retry_after_s = 0.05
        sw._league_start_timeout_s = 0.5
        sw._league_settle_s = 0.0
        sw._league_login_timeout_s = 0.2
        h.api.launch_league_of_legends = self._api

    def _start(self):
        self.running = True
        self.current_login = self.login_as.pop(0) if self.login_as else "same"

    def _api(self):
        self.api_calls += 1
        self.h.api.calls.append("launch_league")
        if "api" in self.start_on:
            self._start()
        if self.api_block_s:
            time.sleep(self.api_block_s)
        return True

    def _exe(self):
        self.exe_calls += 1
        if "exe" in self.start_on:
            self._start()
        return True

    def identity(self):
        if not self.running or self.current_login in (None, "pending"):
            return None
        if self.current_login == "same":
            return "puuid-" + (self.h.api.signed_in_as or "")
        return "puuid-" + self.current_login


def make(start_on=("api",), login_as=None, api_block_s=0.0, identity=True, restart=True):
    h = Harness(IdApi(signed_in_as="main_user"))
    world = LeagueWorld(h, start_on, login_as, api_block_s)
    restarts = []
    if identity:
        h.switcher._league_identity = world.identity
    if restart:
        def _restart():
            restarts.append(1)
            world.running = False
            h.api.running = False
            h.api.signed_in_as = None
        h.switcher._restart_riot_client = _restart
        h.switcher._kill_games = lambda: setattr(world, "running", False) or True
    return h, world, restarts


class LaunchTests(unittest.TestCase):
    def test_league_starts_from_one_api_request(self):
        h, w, _ = make()
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.SUCCESS)
        self.assertTrue(r.league_started)
        self.assertEqual(w.api_calls, 1)
        self.assertEqual(w.exe_calls, 0)

    def test_falls_back_to_riot_client_services_when_the_api_does_nothing(self):
        h, w, _ = make(start_on=("exe",))
        r = h.switcher.switch_to(1)
        self.assertTrue(r.league_started)
        self.assertEqual(w.api_calls, 2)  # first try + one retry
        self.assertEqual(w.exe_calls, 1)

    def test_league_never_starting_is_reported_not_hidden(self):
        h, w, _ = make(start_on=())
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.SUCCESS)
        self.assertIs(r.league_started, False)
        self.assertIn("press Play", r.message)

    def test_a_slow_launch_request_is_not_repeated_while_open(self):
        # League starts at once but the request stays open (as seen live).
        h, w, _ = make(start_on=("api",), api_block_s=0.4)
        t0 = time.monotonic()
        r = h.switcher.switch_to(1)
        self.assertTrue(r.league_started)
        self.assertEqual(w.api_calls, 1)
        self.assertLess(time.monotonic() - t0, 2.0)

    def test_open_request_and_no_league_skips_to_the_exe_not_a_second_post(self):
        h, w, _ = make(start_on=("exe",), api_block_s=0.3)
        r = h.switcher.switch_to(1)
        self.assertTrue(r.league_started)
        self.assertEqual(w.api_calls, 1)
        self.assertEqual(w.exe_calls, 1)


class AccountMatchTests(unittest.TestCase):
    def test_same_account_is_confirmed(self):
        h, w, restarts = make()
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.SUCCESS)
        self.assertIs(r.league_account_ok, True)
        self.assertEqual(restarts, [])
        self.assertEqual(r.message, "Signed in as Smurf.")

    def test_wrong_league_account_triggers_one_full_restart_and_sign_in(self):
        h, w, restarts = make(login_as=["main_user", "same"])
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.SUCCESS, r)
        self.assertIs(r.league_account_ok, True)
        self.assertEqual(len(restarts), 1)
        self.assertEqual(h.form.typed, [("Smurf_User", SECRET), ("Smurf_User", SECRET)])
        self.assertIn("restarting the Riot Client", " | ".join(h.messages()))

    def test_still_wrong_after_the_restart_is_a_failure_not_a_success(self):
        h, w, restarts = make(login_as=["main_user", "main_user"])
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.LEAGUE_WRONG_ACCOUNT)
        self.assertFalse(r.ok)
        self.assertEqual(len(restarts), 1)

    def test_wrong_account_without_a_restart_hook_fails_honestly(self):
        h, w, restarts = make(login_as=["main_user"], restart=False)
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.LEAGUE_WRONG_ACCOUNT)

    # Seen live 29 Oct 2026: Riot Client on the main, League stuck with no
    # login (404, "<unknown player>"), switch still reported "Signed in".
    def test_stuck_league_login_is_fixed_by_restarting_league_only(self):
        h, w, restarts = make(login_as=["pending", "same"])
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.SUCCESS, r)
        self.assertIs(r.league_account_ok, True)
        self.assertFalse(r.league_login_pending)
        self.assertEqual(restarts, [])  # the Riot Client was left alone
        self.assertEqual(len(h.form.typed), 1)
        self.assertEqual(w.api_calls, 2)  # Play pressed once more
        self.assertIn("pressing Play again", " | ".join(h.messages()))

    def test_still_stuck_after_league_restart_does_one_full_riot_restart(self):
        # The League relaunch also failed live: Riot's login queue refused
        # the token ("Invalid JTI claim"). A fresh Riot sign-in is the fix.
        h, w, restarts = make(login_as=["pending", "pending", "same"])
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.SUCCESS, r)
        self.assertIs(r.league_account_ok, True)
        self.assertEqual(len(restarts), 1)
        self.assertEqual(len(h.form.typed), 2)
        self.assertIn("League still can't log in - restarting the Riot Client",
                      " | ".join(h.messages()))

    def test_riot_remembering_the_session_after_restart_still_signs_out_and_retypes(self):
        # James's diagnosis: the old session survives a window close. When the
        # Riot Client comes back still signed in to the same account, that
        # session is the one League just rejected - it must be signed out
        # (verified) and the account typed in again, not reused.
        h, w, restarts = make(login_as=["pending", "pending", "same"])
        def _restart_keeps_session():
            restarts.append(1)
            w.running = False
            h.api.running = False  # client closes, but remembers who was signed in
        h.switcher._restart_riot_client = _restart_keeps_session
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.SUCCESS, r)
        self.assertEqual(len(restarts), 1)
        self.assertEqual(h.api.calls.count("sign_out"), 2)  # initial switch + after restart
        self.assertEqual(len(h.form.typed), 2)
        self.assertTrue(all(who is None for _, who in h.form.events))

    def test_never_logging_in_is_a_failure_not_a_success(self):
        h, w, restarts = make(login_as=["pending", "pending", "pending"])
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.LEAGUE_LOGIN_FAILED)
        self.assertFalse(r.ok)
        self.assertTrue(r.retryable)
        self.assertNotIn("Signed in as", r.message)
        self.assertEqual(len(restarts), 1)

    def test_stuck_login_without_restart_hooks_fails_honestly(self):
        h, w, restarts = make(login_as=["pending", "pending"], restart=False)
        h.switcher._kill_games = None
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.LEAGUE_LOGIN_FAILED)
        self.assertEqual(w.api_calls, 1)

    def test_league_not_coming_back_after_its_restart_is_reported(self):
        h, w, restarts = make(login_as=["pending"])
        orig = w._api
        def api_once():
            if w.api_calls >= 1:
                w.api_calls += 1
                return True  # second Play does nothing
            return orig()
        h.api.launch_league_of_legends = api_once
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.SUCCESS)
        self.assertIs(r.league_started, False)
        self.assertIn("press Play", r.message)
        self.assertEqual(restarts, [])

    def test_already_active_account_is_also_checked(self):
        h, w, restarts = make(login_as=["main_user", "same"])
        h.api.signed_in_as = "smurf_user"
        r = h.switcher.switch_to(1)
        self.assertIs(r.outcome, SwitchOutcome.ALREADY_ACTIVE, r)
        self.assertEqual(len(restarts), 1)
        self.assertIs(r.league_account_ok, True)

    def test_no_password_in_any_message(self):
        h, w, _ = make(login_as=["main_user", "same"])
        h.switcher.switch_to(1)
        self.assertNotIn(SECRET, " ".join(h.messages()))


class CaptchaFalsePositiveTests(unittest.TestCase):
    def test_hcaptcha_markup_on_a_quick_sign_in_is_not_announced(self):
        h, w, _ = make()
        h.form.captcha_visible = lambda: True  # the markup is always there
        h.switcher._nudge_after_s = 5.0
        h.switcher.switch_to(1)
        self.assertNotIn("captcha", " ".join(h.messages()).lower())


class LeagueIdentityTests(unittest.TestCase):
    def _res(self, body, status=200):
        res = MagicMock(status_code=status)
        res.json.return_value = body
        return res

    def test_succeeded_login_returns_the_puuid(self):
        get = MagicMock(return_value=self._res({"state": "SUCCEEDED", "puuid": "ABC"}))
        self.assertEqual(league_login_puuid(lambda: {"port": "1", "token": "t"}, get), "abc")

    def test_login_in_progress_is_none(self):
        get = MagicMock(return_value=self._res({"state": "IN_PROGRESS", "puuid": "ABC"}))
        self.assertIsNone(league_login_puuid(lambda: {"port": "1", "token": "t"}, get))

    def test_no_league_is_none_and_makes_no_request(self):
        get = MagicMock()
        self.assertIsNone(league_login_puuid(lambda: {"port": None, "token": None}, get))
        get.assert_not_called()

    def test_repeated_errors_are_logged_once_without_traceback(self):
        import services.accounts.league_identity as li
        li._last_error = None
        get = MagicMock(side_effect=OSError("refused"))
        with patch.object(li.Logger, "debug") as dbg:
            for _ in range(5):
                league_login_puuid(lambda: {"port": "1", "token": "t"}, get)
        self.assertEqual(dbg.call_count, 1)
        self.assertNotIn("exc", dbg.call_args.kwargs)

    def test_errors_are_none(self):
        get = MagicMock(side_effect=OSError("refused"))
        self.assertIsNone(league_login_puuid(lambda: {"port": "1", "token": "t"}, get))

    def test_riot_session_subject(self):
        api = MagicMock()
        api.get_auth_status.return_value = {"subject": "XYZ"}
        self.assertEqual(RiotSession(api).current_subject(), "xyz")
        api.get_auth_status.return_value = None
        self.assertEqual(RiotSession(api).current_subject(), "")


class LaunchRequestTests(unittest.TestCase):
    def test_launch_post_is_sent_once_with_a_long_timeout(self):
        import requests
        from services.account_manager import RiotClientAPI
        api = RiotClientAPI()
        api.is_connected = True
        api.base_url = "https://127.0.0.1:1"
        api.session = MagicMock()
        api.session.request.side_effect = requests.exceptions.Timeout()
        with patch("services.account_manager.time.sleep"):
            self.assertFalse(api.launch_league_of_legends())
        self.assertEqual(api.session.request.call_count, 1)
        self.assertEqual(api.session.request.call_args.kwargs["timeout"], 30.0)

    def test_other_requests_still_retry(self):
        import requests
        from services.account_manager import RiotClientAPI
        api = RiotClientAPI()
        api.is_connected = True
        api.base_url = "https://127.0.0.1:1"
        api.session = MagicMock()
        api.session.request.side_effect = requests.exceptions.Timeout()
        with patch("services.account_manager.time.sleep"):
            api.request("GET", "/x", silent=True)
        self.assertEqual(api.session.request.call_count, 3)


if __name__ == "__main__":
    unittest.main()
