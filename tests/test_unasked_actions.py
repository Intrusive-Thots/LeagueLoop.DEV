"""
Things the engine did to your account without being asked.

Each of these was reachable on a fresh install, with no switch on any screen
and, in two cases, no screen that admitted the behaviour existed at all.
"""
import sys
import types
import unittest
from unittest import mock

if "win32crypt" not in sys.modules:
    _stub = types.ModuleType("win32crypt")
    _stub.CryptProtectData = lambda d, *a, **k: b"enc:" + d
    _stub.CryptUnprotectData = lambda d, *a, **k: (None, b"pw")
    sys.modules["win32crypt"] = _stub

from core.config_keys import (
    CHAT_WARDEN_ENABLED,
    DODGE_BLACKLIST,
    DODGE_BLACKLIST_ENABLED,
)


class ForceCloseTests(unittest.TestCase):
    """`taskkill /F` on the League Client, run with no switch, no try/except
    and Windows-only flags that raise everywhere else."""

    def _engine(self, **cfg):
        from tests.test_automation_draft import engine

        eng = engine(**cfg)
        eng._blacklist = []
        return eng

    def test_nothing_happens_without_the_switch(self):
        eng = self._engine(**{DODGE_BLACKLIST: "someone"})
        with mock.patch("subprocess.run") as run:
            eng._handle_auto_dodge({
                "localPlayerCellId": 1,
                "myTeam": [{"cellId": 2, "summonerId": 9}],
            })
        run.assert_not_called()

    def test_nothing_happens_with_the_switch_but_an_empty_list(self):
        eng = self._engine(**{DODGE_BLACKLIST_ENABLED: True, DODGE_BLACKLIST: ""})
        with mock.patch("subprocess.run") as run:
            eng._handle_auto_dodge({
                "localPlayerCellId": 1,
                "myTeam": [{"cellId": 2, "summonerId": 9}],
            })
        run.assert_not_called()

    def test_the_list_is_re_read_rather_than_frozen_at_startup(self):
        """It used to be parsed once in __init__, so editing it needed a
        restart."""
        eng = self._engine(**{DODGE_BLACKLIST: ""})
        self.assertEqual(eng._dodge_blacklist(), [])
        eng.config.set(DODGE_BLACKLIST, "Someone, Other#EUW")
        self.assertEqual(eng._dodge_blacklist(), ["someone", "other#euw"])

    def test_a_list_form_value_is_accepted_too(self):
        eng = self._engine(**{DODGE_BLACKLIST: ["A", " b "]})
        self.assertEqual(eng._dodge_blacklist(), ["a", "b"])

    def test_it_refuses_to_run_off_windows_instead_of_raising(self):
        """The Windows-only creationflags raised straight into the tick's
        error killswitch on any other platform."""
        eng = self._engine()
        with mock.patch("sys.platform", "linux"), \
                mock.patch("subprocess.run") as run:
            self.assertFalse(eng._force_close_client("test"))
        run.assert_not_called()

    def test_a_failure_to_close_is_reported_not_raised(self):
        eng = self._engine()
        with mock.patch("sys.platform", "win32"), \
                mock.patch("subprocess.run", side_effect=OSError("nope")):
            self.assertFalse(eng._force_close_client("test"))


class ChatWardenTests(unittest.TestCase):
    """It read every message in the lobby, every tick, gated on nothing."""

    def _engine(self, **cfg):
        from tests.test_automation_draft import engine

        return engine(**cfg)

    def test_off_by_default(self):
        eng = self._engine()
        eng._handle_chat_warden({"chatDetails": {"chatRoomName": "room"}})
        self.assertEqual(eng.lcu.calls, [])

    def test_it_reads_chat_only_when_switched_on(self):
        eng = self._engine(**{CHAT_WARDEN_ENABLED: True})
        eng._chat_warden_warned = False
        eng._toxic_keywords = ["kys"]
        eng._handle_chat_warden({"chatDetails": {"chatRoomName": "room"}})
        self.assertTrue(any("/lol-chat/" in c[1] for c in eng.lcu.calls))


class OfflineQueueTests(unittest.TestCase):
    """An irreversible action that was queued while disconnected replayed
    minutes later, multiplied, with no UI anywhere."""

    def test_loot_crafts_are_never_queued(self):
        from services.api_handler import LCUClient

        self.assertFalse(
            LCUClient._may_queue_offline("/lol-loot/v1/recipes/CHEST_open/craft")
        )
        self.assertFalse(
            LCUClient._may_queue_offline(
                "/lol-loot/v1/recipes/CHEST_open/craft?repeat=8"
            )
        )

    def test_draft_actions_and_ready_checks_are_never_queued(self):
        from services.api_handler import LCUClient

        for endpoint in (
            "/lol-champ-select/v1/session/actions/7",
            "/lol-champ-select/v1/session/my-selection/reroll",
            "/lol-champ-select/v1/session/bench/swap/64",
            "/lol-matchmaking/v1/ready-check/accept",
            "/lol-honor-v2/v1/honor-player",
        ):
            self.assertFalse(LCUClient._may_queue_offline(endpoint), endpoint)

    def test_ordinary_writes_still_queue(self):
        from services.api_handler import LCUClient

        self.assertTrue(LCUClient._may_queue_offline("/lol-chat/v1/me"))
        self.assertTrue(
            LCUClient._may_queue_offline("/lol-lobby/v2/lobby/matchmaking/search")
        )


class CredentialTests(unittest.TestCase):
    """`_encrypt` logged and returned "", so the account was stored with an
    empty password and reported as added."""

    def test_encryption_failure_raises(self):
        from services.account_manager import (
            AccountManager, CredentialEncryptionError,
        )

        with mock.patch("services.account_manager.win32crypt") as crypt:
            crypt.CryptProtectData.side_effect = OSError("DPAPI is unhappy")
            with self.assertRaises(CredentialEncryptionError):
                AccountManager._encrypt("hunter2")

    def test_no_wallet_or_region_is_invented_on_migration(self):
        from services.account_manager import AccountManager
        import inspect

        source = inspect.getsource(AccountManager._migrate_accounts)
        self.assertNotIn('"wallet"', source)
        self.assertNotIn('"region"', source)


if __name__ == "__main__":
    unittest.main()
