"""
Findings from the first real Windows run against a live Riot/League client.

Everything in this repository had, until now, only ever been exercised
against fakes written in this same repository. `qt_startup.log` from a real
session is the first evidence, and it contained two things worth pinning.
"""
import sys
import types
import unittest
from unittest import mock

# The account manager imports DPAPI at module scope; it is Windows-only and
# the test suite is headless. Same stub the other account tests use.
if "win32crypt" not in sys.modules:
    _stub = types.ModuleType("win32crypt")
    _stub.CryptProtectData = lambda d, *a, **k: b"enc:" + d
    _stub.CryptUnprotectData = lambda d, *a, **k: (None, b"pw")
    sys.modules["win32crypt"] = _stub


class ExpectedAbsenceTests(unittest.TestCase):
    """94% of a real 6,098-line log was warnings about a healthy client.

    `GET /lol-lobby/v2/lobby` 404s when you are not in a lobby, and
    `/lol-matchmaking/v1/search` 404s when you are not searching. Both were
    logged as errors — 3,255 and 2,500 times in one session — and both fed an
    anomaly detector that then warned about the error rate they created.
    """

    def _client(self):
        from services.api_handler import LCUClient

        return LCUClient

    def test_a_404_from_an_absent_lobby_is_not_an_error(self):
        c = self._client()
        self.assertTrue(c._is_expected_absence(404, "/lol-lobby/v2/lobby"))
        self.assertTrue(c._is_expected_absence(404, "/lol-matchmaking/v1/search"))
        self.assertTrue(c._is_expected_absence(404, "/lol-champ-select/v1/session"))

    def test_query_strings_and_trailing_slashes_still_match(self):
        c = self._client()
        self.assertTrue(c._is_expected_absence(404, "/lol-lobby/v2/lobby/"))
        self.assertTrue(c._is_expected_absence(404, "/lol-lobby/v2/lobby?x=1"))
        self.assertTrue(
            c._is_expected_absence(404, "/lol-champ-select/v1/session/actions/7")
        )

    def test_a_real_404_elsewhere_is_still_an_error(self):
        c = self._client()
        self.assertFalse(c._is_expected_absence(404, "/lol-summoner/v1/current-summoner"))
        self.assertFalse(c._is_expected_absence(404, "/lol-loot/v1/player-loot"))

    def test_other_statuses_are_never_excused(self):
        c = self._client()
        for code in (400, 401, 403, 429, 500, 503):
            self.assertFalse(c._is_expected_absence(code, "/lol-lobby/v2/lobby"), code)

    def test_an_unrelated_endpoint_with_a_similar_prefix_is_not_excused(self):
        c = self._client()
        self.assertFalse(
            c._is_expected_absence(404, "/lol-lobby/v2/lobby-other-thing")
        )


class SignInPromptTests(unittest.TestCase):
    """The authenticator is a state machine, and only its last step was ever
    being called.

    Two real runs pinned it down:
      * `POST /rso-authenticator/v1/authentication` -> 405 WRONG_METHOD
      * `DELETE` -> 204, but the following PUT still said `invalid_prompt`,
        because clearing a prompt is not the same as opening one.
    """

    def _api(self, responses):
        from services.account_manager import RiotClientAPI

        api = RiotClientAPI.__new__(RiotClientAPI)
        api.calls = []

        def request(method, endpoint, data=None, silent=False):
            api.calls.append((method, endpoint))
            return responses.get((method, endpoint))

        api.request = request
        return api

    def _resp(self, status, payload=None, text=""):
        r = mock.Mock()
        r.status_code = status
        r.json.return_value = payload if payload is not None else {}
        r.text = text
        r.headers = {}
        return r

    def _ok_flow(self, complete_status=200, complete_body=None):
        from services.account_manager import RiotClientAPI as R

        return {
            ("DELETE", R.RSO_RESET): self._resp(204),
            ("POST", R.RSO_START): self._resp(201),
            ("PUT", R.RSO_COMPLETE): self._resp(
                complete_status, complete_body or {"type": "success"}
            ),
        }

    def test_a_prompt_is_opened_before_credentials_are_sent(self):
        from services.account_manager import RiotClientAPI as R

        api = self._api(self._ok_flow())
        result = api.sign_in("someone", "secret")
        self.assertEqual(
            api.calls,
            [("DELETE", R.RSO_RESET), ("POST", R.RSO_START),
             ("PUT", R.RSO_COMPLETE)],
        )
        self.assertEqual(result.get("type"), "success")

    def test_credentials_are_never_sent_when_no_prompt_could_be_opened(self):
        """Otherwise the account is signed out for nothing, every time."""
        from services.account_manager import RiotClientAPI as R

        api = self._api({
            ("DELETE", R.RSO_RESET): self._resp(204),
            ("POST", R.RSO_START): self._resp(405, text="WRONG_METHOD"),
        })
        result = api.sign_in("someone", "secret")
        self.assertNotIn(("PUT", R.RSO_COMPLETE), api.calls)
        self.assertNotIn(("PUT", R.RSO_RESET), api.calls)
        self.assertEqual(result.get("error"), "could_not_start_authentication")

    def test_a_failed_reset_does_not_stop_the_sign_in(self):
        """Nothing to clear is not a reason to refuse to sign in."""
        from services.account_manager import RiotClientAPI as R

        flow = self._ok_flow()
        flow[("DELETE", R.RSO_RESET)] = self._resp(404)
        api = self._api(flow)
        self.assertEqual(api.sign_in("someone", "secret").get("type"), "success")

    def test_an_older_client_falls_back_to_the_legacy_path(self):
        from services.account_manager import RiotClientAPI as R

        flow = self._ok_flow()
        flow[("PUT", R.RSO_COMPLETE)] = self._resp(404)
        flow[("PUT", R.RSO_RESET)] = self._resp(200, {"type": "success"})
        api = self._api(flow)
        result = api.sign_in("someone", "secret")
        self.assertIn(("PUT", R.RSO_RESET), api.calls)
        self.assertEqual(result.get("type"), "success")

    def test_a_missing_riot_client_does_not_send_credentials(self):
        from services.account_manager import RiotClientAPI as R

        api = self._api({})  # every request returns None
        result = api.sign_in("someone", "secret")
        self.assertNotIn(("PUT", R.RSO_COMPLETE), api.calls)
        self.assertEqual(result.get("error"), "could_not_start_authentication")

    def test_two_factor_is_passed_back_rather_than_swallowed(self):
        api = self._api(self._ok_flow(complete_body={"type": "multifactor"}))
        self.assertEqual(api.sign_in("a", "b").get("type"), "multifactor")


class EndpointDiscoveryTests(unittest.TestCase):
    """After two wrong guesses, a failure should report what the client
    actually serves instead of inviting a third."""

    def _api(self, responses):
        from services.account_manager import RiotClientAPI

        api = RiotClientAPI.__new__(RiotClientAPI)
        api.calls = []

        def request(method, endpoint, data=None, silent=False):
            api.calls.append((method, endpoint))
            return responses.get((method, endpoint))

        api.request = request
        return api

    def _resp(self, status, payload=None):
        r = mock.Mock()
        r.status_code = status
        r.json.return_value = payload or {}
        r.text = ""
        r.headers = {}
        return r

    def test_the_openapi_description_is_read_on_failure(self):
        from services.account_manager import RiotClientAPI as R

        doc = {"paths": {
            "/rso-authenticator/v1/authentication": {"get": {}, "delete": {}},
            "/rso-authenticator/v1/authentication/riot-identity/start": {"post": {}},
            "/lol-summoner/v1/current-summoner": {"get": {}},
        }}
        api = self._api({
            ("DELETE", R.RSO_RESET): self._resp(204),
            ("POST", R.RSO_START): self._resp(405),
            ("GET", "/swagger/v3/openapi.json"): self._resp(200, doc),
        })
        api.sign_in("someone", "secret")
        self.assertIn(("GET", "/swagger/v3/openapi.json"), api.calls)

    def test_discovery_failing_is_not_itself_fatal(self):
        from services.account_manager import RiotClientAPI as R

        api = self._api({
            ("DELETE", R.RSO_RESET): self._resp(204),
            ("POST", R.RSO_START): self._resp(405),
        })
        result = api.sign_in("someone", "secret")
        self.assertEqual(result.get("error"), "could_not_start_authentication")


if __name__ == "__main__":
    unittest.main()
