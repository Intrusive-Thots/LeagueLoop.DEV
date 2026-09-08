"""
AccountSwitcher — change account by moving the session, not by typing a password.

What changed, and why
---------------------
The previous sequence signed out through the Riot Client's local API and then
signed in with a stored password. That cannot work any more: Riot's credential
sign-in carries an hCaptcha challenge, so the request is refused with
`invalid_prompt` — the error this project chased through three separate
implementations. `vault.py` has the full account of it.

So the switch is now a file operation, which is what account switchers that
work in practice actually do::

    PREPARING          the account exists, and has a session worth restoring
    CAPTURING          save whoever is signed in right now, before replacing them
    CLOSING_CLIENT     stop League and the Riot Client
    RESTORING_SESSION  swap in the target account's session files
    LAUNCHING          start the Riot Client again (and League, if asked)
    WAITING_FOR_CLIENT wait for it to come up
    VERIFYING          confirm the client agrees about who is signed in
    DONE | FAILED

Three properties this sequence has that the old one did not:

**Nothing is destroyed before it is proven possible.** The target's session is
checked for existence and age *first*. A switch that cannot succeed does not
close your client to find that out.

**Switching away does not lose the account you left.** `CAPTURING` snapshots
the live session before it is overwritten, so switching A → B → A does not ask
you to sign in to A again.

**The client is stopped, not just asked politely.** It holds the session files
open and rewrites them on exit, so a swap underneath a live client is either
refused by Windows or silently undone a moment later.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

from services.accounts.results import (
    EVENT_SWITCH_FINISHED,
    EVENT_SWITCH_PROGRESS,
    EVENT_SWITCH_STARTED,
    OP_SIGN_OUT,
    SwitchOutcome,
    SwitchPhase,
    SwitchProgress,
    SwitchResult,
)
from services.accounts.session import RiotSession
from services.accounts.vault import SessionVault
from utils.logger import Logger

TAG = "AccountSwitch"

#: Everything that must be gone before the session files can be swapped. The
#: Riot Client is last because closing League first is what lets it exit
#: cleanly rather than being killed mid-write.
GAME_PROCESSES = ("LeagueClient.exe", "LeagueClientUx.exe")
CLIENT_PROCESS = "RiotClientServices.exe"

DEFAULT_SIGN_OUT_TIMEOUT_S = 12.0
DEFAULT_CLIENT_TIMEOUT_S = 30.0
#: How long to wait for the Riot Client to actually disappear after being
#: asked to close. Beyond this the files are still open and the swap is unsafe.
DEFAULT_SHUTDOWN_TIMEOUT_S = 15.0
#: Windows releases file handles a moment after the process exits.
POST_SHUTDOWN_SETTLE_S = 0.6


class AccountSwitcher:
    """Runs account switches as one ordered, observable sequence.

    Owns no storage: the account list stays in AccountManager and the saved
    sessions stay in SessionVault. This object only sequences the steps.
    """

    def __init__(
        self,
        session: RiotSession,
        accounts_provider: Callable[[], List[Dict[str, Any]]],
        vault: SessionVault,
        on_success: Optional[Callable[[int], None]] = None,
        on_signed_out: Optional[Callable[[], None]] = None,
        kill_games: Optional[Callable[[], bool]] = None,
        stop_client: Optional[Callable[[], bool]] = None,
        client_running: Optional[Callable[[], bool]] = None,
        launch_client: Optional[Callable[[bool], None]] = None,
        bus: Any = None,
        sign_out_timeout_s: float = DEFAULT_SIGN_OUT_TIMEOUT_S,
        client_timeout_s: float = DEFAULT_CLIENT_TIMEOUT_S,
        shutdown_timeout_s: float = DEFAULT_SHUTDOWN_TIMEOUT_S,
        settle_s: float = POST_SHUTDOWN_SETTLE_S,
    ):
        self.session = session
        self.vault = vault
        self._accounts = accounts_provider
        self._on_success = on_success
        self._on_signed_out = on_signed_out
        self._kill_games = kill_games
        self._stop_client = stop_client
        self._client_running = client_running
        self._launch_client = launch_client
        self._bus = bus
        self._sign_out_timeout_s = sign_out_timeout_s
        self._client_timeout_s = client_timeout_s
        self._shutdown_timeout_s = shutdown_timeout_s
        self._settle_s = settle_s

        # ONE lock for every account operation. The old code had a login-only
        # flag that sign_out ignored, so you could sign out halfway through a
        # login.
        self._lock = threading.Lock()
        self._phase = SwitchPhase.IDLE
        self._current_label = ""

    # ------------------------------------------------------------- state
    @property
    def phase(self) -> SwitchPhase:
        return self._phase

    @property
    def busy(self) -> bool:
        return self._phase not in (
            SwitchPhase.IDLE, SwitchPhase.DONE, SwitchPhase.FAILED,
        )

    # ------------------------------------------------------------ events
    def _emit(self, channel: str, payload: Any) -> None:
        if self._bus is None:
            return
        try:
            self._bus.emit(channel, payload)
        except Exception as exc:
            # A dropped event means the UI never hears the switch finished and
            # sits disabled forever. That is worth a line.
            Logger.error(
                TAG,
                f"Could not publish '{channel}' — the interface will not be "
                f"told about this step.",
                exc=exc, channel=channel,
            )

    def _progress(self, phase: SwitchPhase, message: str, index: int = -1) -> None:
        self._phase = phase
        Logger.info(
            TAG,
            f"{getattr(phase, 'name', phase)}: {message}",
            phase=getattr(phase, "name", str(phase)),
            account_index=index,
        )
        self._emit(
            EVENT_SWITCH_PROGRESS,
            SwitchProgress(
                phase=phase, message=message, account_index=index,
                account_label=self._current_label,
            ),
        )

    def _finish(self, result: SwitchResult) -> SwitchResult:
        outcome = getattr(result.outcome, "name", str(result.outcome))
        operation = getattr(result, "operation", "switch")
        label = self._current_label or "account"
        if result.ok:
            Logger.action(
                TAG, f"{operation} succeeded for {label}",
                outcome=outcome, operation=operation,
                account_index=getattr(result, "account_index", -1),
            )
        else:
            Logger.error(
                TAG,
                f"{operation} failed for {label}: {outcome}"
                + (f" — {result.detail}" if getattr(result, "detail", "") else ""),
                outcome=outcome, operation=operation,
                phase=getattr(self._phase, "name", str(self._phase)),
                account_index=getattr(result, "account_index", -1),
            )
        self._phase = SwitchPhase.DONE if result.ok else SwitchPhase.FAILED
        self._emit(EVENT_SWITCH_FINISHED, result)
        self._phase = SwitchPhase.IDLE
        self._current_label = ""
        return result

    # ------------------------------------------------------- identity keys
    @staticmethod
    def account_key(account: Dict[str, Any]) -> str:
        """The name a session is filed under.

        The username, not the display label: the label is a nickname the user
        can rename at will, and renaming it must not orphan the saved session.
        """
        return str(account.get("username") or account.get("label") or "").strip().lower()

    # ----------------------------------------------------------- public API
    def session_info(self, index: int):
        """What is saved for the account at `index`, for the account row."""
        accounts = self._accounts() or []
        if not (0 <= index < len(accounts)):
            return None
        return self.vault.info(self.account_key(accounts[index]))

    def capture_current(self, index: int) -> bool:
        """Remember the session that is signed in right now as this account's.

        Called after the user signs in by hand — the only moment a session
        can be created, now that passwords cannot be replayed.
        """
        accounts = self._accounts() or []
        if not (0 <= index < len(accounts)):
            return False
        return self.vault.capture(self.account_key(accounts[index]))

    def switch_to(self, index: int, launch_league: bool = True) -> SwitchResult:
        """Switch to the account at `index`. Blocking; run on a worker thread.

        Returns a typed SwitchResult in every case — it does not raise.
        """
        if not self._lock.acquire(blocking=False):
            return SwitchResult(SwitchOutcome.BUSY, SwitchPhase.IDLE, index)
        try:
            return self._switch_locked(index, launch_league)
        except Exception as exc:  # never let a switch escape as an exception
            return self._finish(
                SwitchResult(
                    SwitchOutcome.ERROR, self._phase, index,
                    self._current_label, str(exc),
                )
            )
        finally:
            self._lock.release()

    def sign_out(self) -> SwitchResult:
        """Sign out whoever is signed in. Same lock, same outcomes."""
        if not self._lock.acquire(blocking=False):
            return SwitchResult(
                SwitchOutcome.BUSY, SwitchPhase.IDLE, operation=OP_SIGN_OUT
            )
        try:
            self._emit(
                EVENT_SWITCH_STARTED,
                SwitchProgress(SwitchPhase.PREPARING, "Signing out"),
            )
            outcome = self._ensure_signed_out()
            if outcome is not None:
                return self._finish(
                    SwitchResult(
                        outcome, SwitchPhase.SIGNING_OUT, operation=OP_SIGN_OUT
                    )
                )
            # NB: _ensure_signed_out already fired on_signed_out; calling it
            # again here would double-write the active-account state.
            return self._finish(
                SwitchResult(
                    SwitchOutcome.SUCCESS, SwitchPhase.DONE, operation=OP_SIGN_OUT
                )
            )
        except Exception as exc:
            return self._finish(
                SwitchResult(
                    SwitchOutcome.ERROR, self._phase,
                    detail=str(exc), operation=OP_SIGN_OUT,
                )
            )
        finally:
            self._lock.release()

    # ------------------------------------------------------------ sequence
    def _switch_locked(self, index: int, launch_league: bool) -> SwitchResult:
        accounts = self._accounts() or []
        if not (0 <= index < len(accounts)):
            return self._finish(
                SwitchResult(
                    SwitchOutcome.INVALID_ACCOUNT, SwitchPhase.PREPARING, index
                )
            )

        account = accounts[index]
        label = str(account.get("label") or account.get("username") or "Account")
        key = self.account_key(account)
        self._current_label = label

        self._emit(
            EVENT_SWITCH_STARTED,
            SwitchProgress(
                SwitchPhase.PREPARING, "Switching to {}".format(label), index, label
            ),
        )

        # --- 1. is this switch even possible? -----------------------------
        # Checked before anything is closed. A switch that cannot succeed must
        # not take your running client down to discover that.
        info = self.vault.info(key)
        if not info.exists:
            return self._finish(
                SwitchResult(
                    SwitchOutcome.NO_SAVED_SESSION, SwitchPhase.PREPARING,
                    index, label, info.describe(),
                )
            )
        if not info.usable:
            return self._finish(
                SwitchResult(
                    SwitchOutcome.SESSION_EXPIRED, SwitchPhase.PREPARING,
                    index, label, info.describe(),
                )
            )

        # --- 2. already there? --------------------------------------------
        if self._already_active(key):
            if self._on_success:
                self._safely(self._on_success, index)
            return self._finish(
                SwitchResult(
                    SwitchOutcome.ALREADY_ACTIVE, SwitchPhase.DONE, index, label
                )
            )

        # --- 3. keep the account we are leaving -----------------------------
        self._capture_outgoing(index)

        # --- 4. stop everything holding the files ---------------------------
        self._progress(SwitchPhase.CLOSING_CLIENT, "Closing the Riot Client", index)
        if not self._shut_down_client():
            return self._finish(
                SwitchResult(
                    SwitchOutcome.CLIENT_STILL_RUNNING, SwitchPhase.CLOSING_CLIENT,
                    index, label,
                )
            )

        # --- 5. swap the session -------------------------------------------
        self._progress(
            SwitchPhase.RESTORING_SESSION, "Restoring {}'s session".format(label), index
        )
        if not self.vault.restore(key):
            return self._finish(
                SwitchResult(
                    SwitchOutcome.ERROR, SwitchPhase.RESTORING_SESSION,
                    index, label, "The saved session could not be restored.",
                )
            )

        if self._on_signed_out:
            self._safely(self._on_signed_out)

        # --- 6. bring it back up --------------------------------------------
        self._progress(SwitchPhase.LAUNCHING, "Starting the Riot Client", index)
        if self._launch_client:
            self._safely(self._launch_client, launch_league)

        self._progress(SwitchPhase.WAITING_FOR_CLIENT, "Waiting for the client", index)
        if not self.session.wait_until_client_ready(self._client_timeout_s):
            return self._finish(
                SwitchResult(
                    SwitchOutcome.CLIENT_NOT_RUNNING, SwitchPhase.WAITING_FOR_CLIENT,
                    index, label,
                )
            )

        # --- 7. did the client accept the session? --------------------------
        # The honest check. A restored-but-rejected session leaves the client
        # on a login screen, and reporting success there is the single most
        # misleading thing this sequence could do.
        self._progress(SwitchPhase.VERIFYING, "Confirming the account", index)
        if not self.session.wait_until_signed_in(self._client_timeout_s):
            return self._finish(
                SwitchResult(
                    SwitchOutcome.SESSION_EXPIRED, SwitchPhase.VERIFYING, index, label,
                    "The Riot Client did not accept the saved session. Sign in "
                    "once by hand to refresh it.",
                )
            )

        if self._on_success:
            self._safely(self._on_success, index)

        # The client rewrites the session on a successful sign-in, so what is
        # on disk now is fresher than what we restored. Re-capturing resets
        # the clock and is the reason regular use keeps a session alive.
        self.vault.capture(key)

        return self._finish(
            SwitchResult(SwitchOutcome.SUCCESS, SwitchPhase.DONE, index, label)
        )

    # ------------------------------------------------------------- helpers
    def _already_active(self, key: str) -> bool:
        """Is `key` the account the client is signed in as right now?"""
        if not key:
            return False
        try:
            if not self.session.connect() or not self.session.is_signed_in():
                return False
            return self.session.current_login_name() == key
        except Exception as exc:
            Logger.debug(TAG, "Could not read the current account", exc=exc)
            return False

    def _capture_outgoing(self, index: int) -> None:
        """Save the live session under whichever account it belongs to.

        Best effort by design: failing to keep the outgoing account is a
        smaller harm than refusing the switch the user asked for. It is logged
        so a pattern of failures is visible.
        """
        if not self.vault.live_session_present():
            return
        try:
            current = self.session.current_login_name()
        except Exception:
            current = ""
        if not current:
            Logger.debug(
                TAG,
                "A session is present but the client did not say whose; not "
                "capturing it.",
            )
            return
        self._progress(
            SwitchPhase.CAPTURING, "Saving the current session", index
        )
        self.vault.capture(current)

    def _shut_down_client(self) -> bool:
        """Stop League and the Riot Client, and confirm they are gone."""
        if self._kill_games:
            self._safely(self._kill_games)
        if self._stop_client:
            self._safely(self._stop_client)

        if self._client_running is None:
            # No way to observe it. Assume the caller's stop worked rather
            # than blocking the switch, but say so — a swap under a live
            # client is silently undone and that is very hard to diagnose.
            Logger.warning(
                TAG,
                "No way to check whether the Riot Client actually closed; "
                "continuing, but the session swap may not stick.",
            )
            return True

        deadline = time.monotonic() + self._shutdown_timeout_s
        while time.monotonic() < deadline:
            try:
                if not self._client_running():
                    # Windows releases the file handles a moment after exit.
                    time.sleep(self._settle_s)
                    return True
            except Exception as exc:
                Logger.debug(TAG, "Could not check the client process", exc=exc)
                return True
            time.sleep(0.3)
        return False

    def _ensure_signed_out(self, index: int = -1) -> Optional[SwitchOutcome]:
        """Sign out whoever is signed in. Returns None on success, else why not.

        League must be closed first — the Riot Client refuses sign-out with
        `sign_out_failed_other_games_running` while it is up.
        """
        if not self.session.connect():
            return SwitchOutcome.CLIENT_UNREACHABLE

        if not self.session.is_signed_in():
            return None

        # Keep the session before signing out of it, or signing out silently
        # costs the user their ability to switch back without a password.
        self._capture_outgoing(index)

        self._progress(SwitchPhase.SIGNING_OUT, "Closing League", index)
        if self._kill_games:
            self._safely(self._kill_games)

        self._progress(SwitchPhase.SIGNING_OUT, "Signing out", index)
        self.session.sign_out()

        # Verify rather than assuming, and rather than sleeping a fixed 2s.
        if not self.session.wait_until_signed_out(self._sign_out_timeout_s):
            return SwitchOutcome.SIGN_OUT_FAILED

        if self._on_signed_out:
            self._safely(self._on_signed_out)
        return None

    @staticmethod
    def _safely(fn: Callable, *args) -> Any:
        """Call an injected callback without letting it break the sequence."""
        try:
            return fn(*args)
        except Exception as exc:
            Logger.debug(TAG, "A switch callback failed", exc=exc)
            return None
