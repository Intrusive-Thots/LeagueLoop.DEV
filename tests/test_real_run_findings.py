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


if __name__ == "__main__":
    unittest.main()
