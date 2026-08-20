"""
`detect_active_account()` end-to-end against fake clients.

The old version wrote `_active_idx` and `accounts.json` from a background
thread without the lock, and silently created accounts with no password when
it did not recognise who was signed in. These tests pin the replacement.
"""
import json
import os
import sys
import tempfile
import types
import unittest

if "win32crypt" not in sys.modules:
    stub = types.ModuleType("win32crypt")
    stub.CryptProtectData = lambda d, *a, **k: b"enc:" + d
    stub.CryptUnprotectData = lambda d, *a, **k: (None, b"pw")
    sys.modules["win32crypt"] = stub

import services.account_manager as am

ACCOUNTS = [
    {"label": "Main", "username": "themalcolm3", "tagline": "dpm#null",
     "last_used": None},
    {"label": "Smurf", "username": "dpmnull2", "tagline": "", "last_used": None},
]


class FakeRiotClient:
    def __init__(self, userinfo=None, connects=True):
        self._userinfo = userinfo
        self._connects = connects
        self.is_connected = False

    def connect(self):
        self.is_connected = self._connects
        return self._connects

    def get_current_user(self):
        return self._userinfo


class FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


class FakeLcu:
    def __init__(self, summoner=None, wallet=None):
        self.is_connected = True
        self._summoner = summoner
        self._wallet = wallet

    def request(self, method, endpoint, silent=False):
        if "current-summoner" in endpoint and self._summoner is not None:
            return FakeResponse(self._summoner)
        if "wallet" in endpoint and self._wallet is not None:
            return FakeResponse(self._wallet)
        return None


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "accounts.json")
        original = am.ACCOUNTS_FILE
        am.ACCOUNTS_FILE = self.path
        self.addCleanup(lambda: setattr(am, "ACCOUNTS_FILE", original))
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"accounts": [dict(a) for a in ACCOUNTS],
                       "active_account_idx": -1}, f)

    def _manager(self, userinfo=None, lcu=None, connects=True):
        manager = am.AccountManager(lcu=lcu)
        manager.riot_client = FakeRiotClient(userinfo, connects=connects)
        return manager

    # ------------------------------------------------------------ matching
    def test_matches_by_login_username(self):
        manager = self._manager({"preferred_username": "dpmnull2"})
        self.assertEqual(manager.detect_active_account(), 1)
        self.assertEqual(manager.get_active_index(), 1)
        self.assertIsNone(manager.get_unrecognised_identity())

    def test_falls_back_to_the_lcu_when_the_riot_client_says_nothing(self):
        manager = self._manager(
            None, lcu=FakeLcu(summoner={"gameName": "DPM", "tagLine": "Null"})
        )
        self.assertEqual(manager.detect_active_account(), 0)

    def test_backfills_a_missing_riot_id_on_the_matched_account(self):
        manager = self._manager({
            "preferred_username": "dpmnull2",
            "acct": {"game_name": "Smurfy", "tag_line": "NA1"},
        })
        manager.detect_active_account()
        self.assertEqual(manager.get_accounts()[1]["tagline"], "smurfy#na1")

    def test_never_overwrites_an_existing_riot_id(self):
        manager = self._manager({
            "preferred_username": "themalcolm3",
            "acct": {"game_name": "Different", "tag_line": "XX"},
        })
        manager.detect_active_account()
        self.assertEqual(manager.get_accounts()[0]["tagline"], "dpm#null")

    # ------------------------------------------------------ no silent junk
    def test_an_unknown_account_is_reported_not_created(self):
        manager = self._manager({
            "preferred_username": "stranger",
            "acct": {"game_name": "Stranger", "tag_line": "NA1"},
        })
        self.assertEqual(manager.detect_active_account(), -1)
        self.assertEqual(len(manager.get_accounts()), 2, "an account was invented")

        identity = manager.get_unrecognised_identity()
        self.assertIsNotNone(identity)
        self.assertEqual(identity["username"], "stranger")
        self.assertEqual(identity["tagline"], "stranger#na1")

    def test_a_label_coincidence_does_not_repoint_the_active_account(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"accounts": [
                {"label": "stranger", "username": "someone", "tagline": ""},
            ], "active_account_idx": -1}, f)
        manager = self._manager({"acct": {"game_name": "Stranger", "tag_line": "NA1"}})

        self.assertEqual(manager.detect_active_account(), -1)
        self.assertIsNotNone(manager.get_unrecognised_identity())

    def test_recognising_an_account_clears_a_previous_unknown(self):
        manager = self._manager({"preferred_username": "stranger"})
        manager.detect_active_account()
        self.assertIsNotNone(manager.get_unrecognised_identity())

        manager.riot_client = FakeRiotClient({"preferred_username": "themalcolm3"})
        manager.detect_active_account()
        self.assertIsNone(manager.get_unrecognised_identity())

    def test_nobody_signed_in_is_not_an_unknown_account(self):
        manager = self._manager(None)
        manager.detect_active_account()
        self.assertIsNone(manager.get_unrecognised_identity())

    # --------------------------------------------------------- persistence
    def test_detection_does_not_rewrite_the_file_when_nothing_changed(self):
        manager = self._manager({"preferred_username": "themalcolm3"})
        manager.detect_active_account()
        before = os.stat(self.path).st_mtime_ns

        for _ in range(3):
            manager.detect_active_account()

        self.assertEqual(os.stat(self.path).st_mtime_ns, before)

    # -------------------------------------------------------------- wallet
    def test_wallet_is_cached_for_the_active_account(self):
        lcu = FakeLcu(wallet={"RP": 1350, "lol_blue_essence": 42000})
        manager = self._manager({"preferred_username": "themalcolm3"}, lcu=lcu)
        manager.detect_active_account()
        self.assertEqual(manager.get_accounts()[0]["wallet"],
                         {"be": 42000, "rp": 1350})

    def test_wallet_survives_the_active_account_being_removed_mid_flight(self):
        """The old version indexed _active_idx read outside the lock."""
        lcu = FakeLcu(wallet={"RP": 1, "lol_blue_essence": 2})
        manager = self._manager({"preferred_username": "themalcolm3"}, lcu=lcu)
        manager._active_idx = 99  # stale index, as after a concurrent delete
        manager._update_wallet()  # must not raise


if __name__ == "__main__":
    unittest.main()
