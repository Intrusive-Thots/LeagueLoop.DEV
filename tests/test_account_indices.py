"""
Account list indices must be stable.

`get_accounts()` used to sort the underlying list by `last_used`, recompute
the active index and write accounts.json - inside a getter. Since `last_used`
changes on every successful sign-in, the row the user saw could point at a
different account by the time they clicked "Switch". These tests pin the
getter as a pure read and cover the display-ordering helper that replaced it.
"""
import json
import os
import sys
import tempfile
import types
import unittest

# The manager imports win32crypt at module scope (DPAPI, Windows-only). Stub it
# so the pure list/index logic can be tested anywhere, including CI.
if "win32crypt" not in sys.modules:
    stub = types.ModuleType("win32crypt")
    stub.CryptProtectData = lambda data, *a, **kw: b"enc:" + data
    stub.CryptUnprotectData = lambda data, *a, **kw: (None, data[4:])
    sys.modules["win32crypt"] = stub

import services.account_manager as am


ACCOUNTS = [
    {"label": "Main", "username": "main", "last_used": "2026-01-01T00:00:00"},
    {"label": "Smurf", "username": "smurf", "last_used": "2026-06-01T00:00:00"},
    {"label": "Fresh", "username": "fresh", "last_used": None},
]


class AccountIndexTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "accounts.json")

        self._orig_file = am.ACCOUNTS_FILE
        am.ACCOUNTS_FILE = self.path
        self.addCleanup(lambda: setattr(am, "ACCOUNTS_FILE", self._orig_file))

        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"accounts": [dict(a) for a in ACCOUNTS],
                       "active_account_idx": 0}, f)

        self.manager = am.AccountManager()

    # ------------------------------------------------------------------
    def test_get_accounts_preserves_stored_order(self):
        labels = [a["label"] for a in self.manager.get_accounts()]
        self.assertEqual(labels, ["Main", "Smurf", "Fresh"])

    def test_get_accounts_does_not_mutate_or_persist(self):
        before = os.stat(self.path).st_mtime_ns
        snapshot = [dict(a) for a in self.manager._accounts]
        active_before = self.manager.get_active_index()

        for _ in range(3):
            self.manager.get_accounts()

        self.assertEqual(self.manager._accounts, snapshot)
        self.assertEqual(self.manager.get_active_index(), active_before)
        self.assertEqual(os.stat(self.path).st_mtime_ns, before,
                         "get_accounts() wrote to disk")

    def test_returned_dicts_are_copies(self):
        accounts = self.manager.get_accounts()
        accounts[0]["label"] = "tampered"
        self.assertEqual(self.manager._accounts[0]["label"], "Main")

    def test_index_still_addresses_the_same_account_after_a_sign_in(self):
        """The regression this whole change exists for."""
        index_of_main = 0
        self.assertEqual(self.manager.get_accounts()[index_of_main]["username"], "main")

        # A successful sign-in stamps last_used, which is what used to reorder.
        self.manager._mark_active(2)

        self.assertEqual(self.manager.get_accounts()[index_of_main]["username"], "main")
        self.assertEqual(self.manager.get_active_index(), 2)

    # ------------------------------------------------------------------
    def test_display_order_is_most_recent_first_with_real_indices(self):
        pairs = self.manager.get_accounts_display()
        self.assertEqual(
            [(i, a["label"]) for i, a in pairs],
            [(1, "Smurf"), (0, "Main"), (2, "Fresh")],
        )

    def test_display_indices_address_the_stored_list(self):
        stored = self.manager.get_accounts()
        for index, account in self.manager.get_accounts_display():
            self.assertEqual(stored[index]["username"], account["username"])

    def test_display_tolerates_unparsable_last_used(self):
        self.manager._accounts[0]["last_used"] = "not-a-date"
        pairs = self.manager.get_accounts_display()
        self.assertEqual(len(pairs), 3)
        self.assertEqual(sorted(i for i, _ in pairs), [0, 1, 2])

    def test_display_does_not_persist(self):
        before = os.stat(self.path).st_mtime_ns
        self.manager.get_accounts_display()
        self.assertEqual(os.stat(self.path).st_mtime_ns, before)


if __name__ == "__main__":
    unittest.main()
