"""
Save and restore the Riot Client's own session, instead of replaying a password.

Why this exists
---------------
The switcher used to store the password (DPAPI-encrypted) and POST it to the
Riot Client's local `rso-authenticator` endpoints. That cannot work any more:
Riot's credential sign-in carries an hCaptcha challenge, and a request without
a solved captcha token is refused with `invalid_prompt` — the error this
project chased through three separate implementations before finding out why.

The alternatives are a paid captcha-solving service, or typing the password
into the client window with synthetic keystrokes. This project already removed
the keystroke path once, for a good reason: `pyautogui.write()` sends the
password to whichever window holds focus at that instant.

Riot's own guidance points at the third option — **reuse the session you
already have rather than sending the password again** — and that is what every
account switcher that works in practice actually does: close the client, swap
the local session files, start it again.

What a session is
-----------------
Two things under ``%LOCALAPPDATA%\\Riot Games\\Riot Client\\Data``:

``RiotClientPrivateSettings.yaml``
    the persisted sign-in. Deleting it is the long-standing manual fix for a
    client stuck on the wrong account, which is the same lever from the other
    side.

``Cookies/``
    the cookie jar, including ``ssid``. Sometimes absent on a fresh install —
    a missing directory here is a normal state, not an error.

They belong together. Restoring one without the other gives the client half an
identity, which it resolves by showing a login screen.

Expiry is the part that must be visible
---------------------------------------
Refreshing from the ``ssid`` cookie alone is dependable for roughly a week;
the full cookie set stretches it to roughly three. After that the client shows
a login screen and no amount of automation gets past it. A switcher that
cannot tell a fresh session from a stale one looks broken exactly when it
matters, so every saved session carries its capture time and reports its own
age — see `SessionInfo.freshness`.

Nothing here needs the Riot Client to be running, and nothing here needs a
password. It is file copying, with the client stopped.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from typing import List, Optional

from utils.logger import Logger

TAG = "SessionVault"

#: Files that together make up one signed-in identity, relative to the Riot
#: Client's Data directory. `None` for the directory entry means "a tree".
SESSION_FILE = "RiotClientPrivateSettings.yaml"
COOKIE_DIR = "Cookies"

#: Written beside each saved session so age can be reported without trusting
#: the filesystem's mtime, which copying and syncing both rewrite.
MANIFEST = "session.json"

#: How long a saved session stays useful. The `ssid` cookie alone refreshes
#: reliably for about a week; with the whole cookie jar, about three. Both are
#: observations about Riot's servers, not settings — they are here so the UI
#: can warn before a switch fails rather than after.
FRESH_DAYS = 5.0
STALE_DAYS = 14.0
DEAD_DAYS = 21.0

FRESH = "fresh"
AGEING = "ageing"
STALE = "stale"
EXPIRED = "expired"
MISSING = "missing"


def riot_data_dir() -> str:
    """Where the Riot Client keeps its session, on this machine."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Riot Games", "Riot Client", "Data")


@dataclass(frozen=True)
class SessionInfo:
    """What is known about one account's saved session."""

    account_id: str
    exists: bool
    captured_at: float = 0.0
    has_cookies: bool = False

    @property
    def dated(self) -> bool:
        """False when we do not know when this session was captured."""
        return self.captured_at > 0

    @property
    def age_days(self) -> float:
        if not self.dated:
            # Unknown, not new. Returning 0.0 here would report an undateable
            # session as captured today, which is precisely the lie that
            # matters: the user is told to expect a working switch and gets a
            # login screen.
            return float("inf")
        return max(0.0, (time.time() - self.captured_at) / 86400.0)

    @property
    def freshness(self) -> str:
        """One of MISSING / FRESH / AGEING / STALE / EXPIRED."""
        if not self.exists:
            return MISSING
        if not self.dated:
            return EXPIRED
        age = self.age_days
        if age < FRESH_DAYS:
            return FRESH
        if age < STALE_DAYS:
            return AGEING
        if age < DEAD_DAYS:
            return STALE
        return EXPIRED

    @property
    def usable(self) -> bool:
        """True when restoring this is worth attempting.

        An expired session is not merely unlikely to work — restoring it
        replaces a possibly-good live session with a certainly-dead one, so
        it is worse than doing nothing.
        """
        return self.freshness in (FRESH, AGEING, STALE)

    def describe(self) -> str:
        """A sentence for the account row."""
        if not self.exists:
            return "No saved session — sign in once and it will be remembered."
        if not self.dated:
            return (
                "Saved session cannot be dated, so it is treated as expired. "
                "Sign in by hand to replace it."
            )
        age = self.age_days
        if age < 1:
            return "Session saved today."
        days = int(age)
        plural = "" if days == 1 else "s"
        if self.freshness == FRESH:
            return "Session saved {} day{} ago.".format(days, plural)
        if self.freshness == AGEING:
            return "Session is {} day{} old; it will need refreshing soon.".format(
                days, plural
            )
        if self.freshness == STALE:
            return (
                "Session is {} day{} old and may no longer be accepted. "
                "Sign in once to refresh it.".format(days, plural)
            )
        return (
            "Session is {} day{} old and has almost certainly expired. "
            "Sign in by hand to refresh it.".format(days, plural)
        )


class SessionVault:
    """Stores one saved Riot session per account."""

    def __init__(self, root: str, data_dir: Optional[str] = None):
        #: Where saved sessions live — inside the app's own data directory,
        #: never beside the accounts file, so a corrupt session cannot take
        #: the account list with it.
        self.root = os.path.join(root, "sessions")
        #: The live Riot Client session directory. Injectable for tests.
        self.data_dir = data_dir or riot_data_dir()

    # ----------------------------------------------------------- locations
    def _slot(self, account_id: str) -> str:
        # Account ids come from the account list, which the user names. Keep
        # only characters that cannot escape the directory.
        safe = "".join(c for c in str(account_id) if c.isalnum() or c in "-_")
        return os.path.join(self.root, safe or "unnamed")

    def _live_session(self) -> str:
        return os.path.join(self.data_dir, SESSION_FILE)

    def _live_cookies(self) -> str:
        return os.path.join(self.data_dir, COOKIE_DIR)

    # -------------------------------------------------------------- status
    def info(self, account_id: str) -> SessionInfo:
        """What is saved for this account, and how old it is."""
        slot = self._slot(account_id)
        session = os.path.join(slot, SESSION_FILE)
        if not os.path.exists(session):
            return SessionInfo(account_id=str(account_id), exists=False)

        captured_at = 0.0
        try:
            with open(os.path.join(slot, MANIFEST), encoding="utf-8") as handle:
                captured_at = float(json.load(handle).get("captured_at") or 0.0)
        except Exception:
            # No manifest: fall back to the file's own mtime. Less trustworthy
            # after a copy, but far better than reporting age zero and telling
            # the user a year-old session is fresh.
            try:
                captured_at = os.path.getmtime(session)
            except OSError:
                captured_at = 0.0

        return SessionInfo(
            account_id=str(account_id),
            exists=True,
            captured_at=captured_at,
            has_cookies=os.path.isdir(os.path.join(slot, COOKIE_DIR)),
        )

    def live_session_present(self) -> bool:
        """Is there a signed-in session on this machine right now?"""
        return os.path.exists(self._live_session())

    def saved_accounts(self) -> List[str]:
        try:
            return sorted(
                name for name in os.listdir(self.root)
                if os.path.exists(os.path.join(self.root, name, SESSION_FILE))
            )
        except OSError:
            return []

    # ------------------------------------------------------------- capture
    def capture(self, account_id: str) -> bool:
        """Save the session that is signed in right now, for this account.

        Called after a sign-in that the user did themselves. Returns False
        when there is nothing to capture, which is not a failure — it means
        nobody is signed in.
        """
        live = self._live_session()
        if not os.path.exists(live):
            Logger.info(
                TAG,
                "Nothing to capture: the Riot Client has no stored session.",
            )
            return False

        slot = self._slot(account_id)
        # Write to a scratch slot and swap, so an interrupted capture cannot
        # leave a half-copied session that restore would happily install.
        pending = slot + ".incoming"
        self._remove_tree(pending)
        try:
            os.makedirs(pending, exist_ok=True)
            shutil.copy2(live, os.path.join(pending, SESSION_FILE))

            cookies = self._live_cookies()
            if os.path.isdir(cookies):
                shutil.copytree(cookies, os.path.join(pending, COOKIE_DIR))

            with open(os.path.join(pending, MANIFEST), "w", encoding="utf-8") as handle:
                json.dump(
                    {"captured_at": time.time(), "account_id": str(account_id)},
                    handle,
                )
        except Exception as exc:
            Logger.error(TAG, "Could not capture the Riot session.", exc=exc)
            self._remove_tree(pending)
            return False

        self._remove_tree(slot)
        try:
            os.replace(pending, slot)
        except OSError as exc:
            Logger.error(TAG, "Could not store the captured session.", exc=exc)
            self._remove_tree(pending)
            return False

        Logger.action(TAG, "Saved the Riot session for {}.".format(account_id))
        return True

    # ------------------------------------------------------------- restore
    def restore(self, account_id: str) -> bool:
        """Install this account's saved session as the live one.

        **The Riot Client must not be running.** It holds these files open and
        rewrites them on exit, so restoring underneath a live client either
        fails on Windows or is silently undone a moment later. The caller owns
        stopping it; this refuses to guess.
        """
        info = self.info(account_id)
        if not info.exists:
            Logger.warning(
                TAG, "No saved session for {}.".format(account_id),
            )
            return False
        if not info.usable:
            # Refusing is the kinder answer: restoring a dead session
            # replaces whatever is there with something certain not to work.
            Logger.warning(
                TAG,
                "Refusing to restore an expired session for {} ({:.0f} days "
                "old).".format(account_id, info.age_days),
            )
            return False

        slot = self._slot(account_id)
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            shutil.copy2(os.path.join(slot, SESSION_FILE), self._live_session())

            saved_cookies = os.path.join(slot, COOKIE_DIR)
            live_cookies = self._live_cookies()
            if os.path.isdir(saved_cookies):
                self._remove_tree(live_cookies)
                shutil.copytree(saved_cookies, live_cookies)
            else:
                # No saved jar: clear the live one rather than leaving the
                # previous account's cookies beside this account's session.
                # Mixing the two is how a switch lands on the wrong identity.
                self._remove_tree(live_cookies)
        except Exception as exc:
            Logger.error(TAG, "Could not restore the Riot session.", exc=exc)
            return False

        Logger.action(TAG, "Restored the Riot session for {}.".format(account_id))
        return True

    def forget(self, account_id: str) -> bool:
        """Delete a saved session. Used when an account is removed."""
        slot = self._slot(account_id)
        if not os.path.exists(slot):
            return False
        self._remove_tree(slot)
        Logger.info(TAG, "Forgot the saved session for {}.".format(account_id))
        return True

    # ------------------------------------------------------------ internals
    @staticmethod
    def _remove_tree(path: str) -> None:
        if not os.path.exists(path):
            return
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as exc:
            Logger.debug(TAG, "Could not remove {}".format(path), exc=exc)


__all__ = [
    "AGEING", "COOKIE_DIR", "DEAD_DAYS", "EXPIRED", "FRESH", "FRESH_DAYS",
    "MISSING", "SESSION_FILE", "STALE", "STALE_DAYS", "SessionInfo",
    "SessionVault", "riot_data_dir",
]
