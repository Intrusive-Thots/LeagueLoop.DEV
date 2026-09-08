"""
Account switching by session, not by password.

Riot's credential sign-in now carries an hCaptcha challenge, so the local
`rso-authenticator` flow answers `invalid_prompt` to any request without a
solved token — the error this project chased through three implementations.
The switcher therefore stops replaying passwords and moves the Riot Client's
own session files instead, which is what account switchers that work in
practice actually do.

These tests use a fake Riot data directory. Nothing here touches a real
install, and nothing needs the Riot Client.
"""
import json
import os
import shutil
import tempfile
import time
import unittest

from services.accounts.vault import (
    COOKIE_DIR,
    DEAD_DAYS,
    EXPIRED,
    FRESH,
    SESSION_FILE,
    STALE,
    SessionVault,
    riot_data_dir,
)

DAY = 86400.0


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.live = os.path.join(self.tmp, "riot-data")
        os.makedirs(self.live)
        self.vault = SessionVault(os.path.join(self.tmp, "app"), data_dir=self.live)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _sign_in(self, marker="account-a", cookies=True):
        """Pretend somebody signed in: write the files the client would."""
        with open(os.path.join(self.live, SESSION_FILE), "w", encoding="utf-8") as f:
            f.write("ssid: %s\n" % marker)
        jar = os.path.join(self.live, COOKIE_DIR)
        if cookies:
            os.makedirs(jar, exist_ok=True)
            with open(os.path.join(jar, "Cookies"), "w", encoding="utf-8") as f:
                f.write(marker)
        return marker

    def _live_marker(self):
        with open(os.path.join(self.live, SESSION_FILE), encoding="utf-8") as f:
            return f.read().strip().split(": ")[1]

    def _age(self, account_id, days):
        slot = self.vault._slot(account_id)
        with open(os.path.join(slot, "session.json"), "w", encoding="utf-8") as f:
            json.dump({"captured_at": time.time() - days * DAY}, f)

    # ------------------------------------------------------------- capture
    def test_capturing_with_nobody_signed_in_is_not_an_error(self):
        """There is simply nothing to save yet."""
        self.assertFalse(self.vault.capture("a"))
        self.assertFalse(self.vault.info("a").exists)

    def test_a_captured_session_records_when_it_was_taken(self):
        self._sign_in()
        self.assertTrue(self.vault.capture("a"))
        info = self.vault.info("a")
        self.assertTrue(info.exists)
        self.assertTrue(info.has_cookies)
        self.assertLess(info.age_days, 1)
        self.assertEqual(info.freshness, FRESH)

    def test_capture_survives_a_missing_cookie_directory(self):
        """A fresh install has no Cookies folder; that is normal, not broken."""
        self._sign_in(cookies=False)
        self.assertTrue(self.vault.capture("a"))
        self.assertFalse(self.vault.info("a").has_cookies)

    def test_recapturing_replaces_the_previous_session(self):
        self._sign_in("first")
        self.vault.capture("a")
        self._sign_in("second")
        self.vault.capture("a")
        self.vault.restore("a")
        self.assertEqual(self._live_marker(), "second")

    # ------------------------------------------------------------- restore
    def test_restoring_puts_the_right_account_back(self):
        self._sign_in("alpha")
        self.vault.capture("alpha")
        self._sign_in("beta")
        self.vault.capture("beta")

        self.assertTrue(self.vault.restore("alpha"))
        self.assertEqual(self._live_marker(), "alpha")
        self.assertTrue(self.vault.restore("beta"))
        self.assertEqual(self._live_marker(), "beta")

    def test_restoring_replaces_the_cookie_jar_rather_than_merging_it(self):
        """The previous account's cookies beside this account's session is how
        a switch lands on the wrong identity."""
        self._sign_in("alpha")
        self.vault.capture("alpha")
        self._sign_in("beta")
        with open(os.path.join(self.live, COOKIE_DIR, "extra"), "w") as f:
            f.write("beta-only")

        self.vault.restore("alpha")
        self.assertFalse(os.path.exists(os.path.join(self.live, COOKIE_DIR, "extra")))

    def test_a_session_captured_without_cookies_clears_the_live_jar(self):
        self._sign_in("alpha", cookies=False)
        self.vault.capture("alpha")
        self._sign_in("beta", cookies=True)
        self.vault.restore("alpha")
        self.assertFalse(os.path.isdir(os.path.join(self.live, COOKIE_DIR)))

    def test_restoring_an_unknown_account_fails_without_touching_anything(self):
        self._sign_in("alpha")
        self.assertFalse(self.vault.restore("nobody"))
        self.assertEqual(self._live_marker(), "alpha")

    def test_an_expired_session_is_refused_not_attempted(self):
        """Restoring a dead session replaces a possibly-good live one with a
        certainly-dead one — worse than doing nothing."""
        self._sign_in("alpha")
        self.vault.capture("alpha")
        self._age("alpha", DEAD_DAYS + 2)

        self.assertEqual(self.vault.info("alpha").freshness, EXPIRED)
        self.assertFalse(self.vault.info("alpha").usable)
        self.assertFalse(self.vault.restore("alpha"))

    def test_a_stale_session_is_still_worth_trying(self):
        self._sign_in("alpha")
        self.vault.capture("alpha")
        self._age("alpha", DEAD_DAYS - 2)
        self.assertEqual(self.vault.info("alpha").freshness, STALE)
        self.assertTrue(self.vault.restore("alpha"))

    # -------------------------------------------------------------- ageing
    def test_freshness_moves_through_every_band_as_a_session_ages(self):
        self._sign_in()
        self.vault.capture("a")
        seen = []
        for days in (0, 7, 17, 40):
            self._age("a", days)
            seen.append(self.vault.info("a").freshness)
        self.assertEqual(len(set(seen)), 4, "bands collapsed: %s" % seen)

    def test_a_session_with_no_manifest_is_not_reported_as_brand_new(self):
        """Falling back to age zero would tell the user a year-old session is
        fresh, which is the one lie that matters here."""
        self._sign_in()
        self.vault.capture("a")
        slot = self.vault._slot("a")
        os.remove(os.path.join(slot, "session.json"))
        old = time.time() - 30 * DAY
        os.utime(os.path.join(slot, SESSION_FILE), (old, old))
        self.assertGreater(self.vault.info("a").age_days, 25)

    def test_every_description_says_what_to_do_next(self):
        self._sign_in()
        self.vault.capture("a")
        for days in (0, 7, 17, 40):
            self._age("a", days)
            self.assertTrue(self.vault.info("a").describe().strip())
        self.assertIn("sign in", self.vault.info("nobody").describe().lower())

    # ------------------------------------------------------------ hygiene
    def test_an_account_id_cannot_escape_the_vault_directory(self):
        self._sign_in()
        self.vault.capture("../../etc/evil")
        self.assertTrue(
            os.path.abspath(self.vault._slot("../../etc/evil")).startswith(
                os.path.abspath(self.vault.root)
            )
        )

    def test_forgetting_an_account_removes_its_session(self):
        self._sign_in()
        self.vault.capture("a")
        self.assertTrue(self.vault.forget("a"))
        self.assertFalse(self.vault.info("a").exists)
        self.assertFalse(self.vault.forget("a"))

    def test_saved_accounts_lists_what_is_stored(self):
        self._sign_in()
        self.vault.capture("alpha")
        self.vault.capture("beta")
        self.assertEqual(self.vault.saved_accounts(), ["alpha", "beta"])

    def test_an_interrupted_capture_leaves_no_half_session(self):
        """The swap is what guarantees this: restore must never install a
        session that was only partly copied."""
        self._sign_in()
        self.vault.capture("a")
        pending = self.vault._slot("a") + ".incoming"
        os.makedirs(pending, exist_ok=True)
        with open(os.path.join(pending, SESSION_FILE), "w") as f:
            f.write("half")
        self._sign_in("whole")
        self.vault.capture("a")
        self.vault.restore("a")
        self.assertEqual(self._live_marker(), "whole")


class RiotPathTests(unittest.TestCase):
    def test_the_data_directory_is_the_one_the_client_uses(self):
        path = riot_data_dir().replace("\\", "/")
        self.assertTrue(path.endswith("Riot Games/Riot Client/Data"), path)


if __name__ == "__main__":
    unittest.main()
