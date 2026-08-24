"""
AccountSwitcher — one consistent way to change account.

The previous code had two operations that disagreed with each other:

    sign_out()      killed League, called the Riot Client API, updated state
    login_account() typed the username and password as keystrokes into
                    whatever window had focus, and did *not* sign out first

Because it never signed out, switching only worked if you happened to already
be signed out; otherwise the keystrokes went into the Riot Client UI as
random input. Meanwhile `RiotClientAPI.sign_in()` — a proper API sign-in that
already handled 2FA and error codes — was never called by anything.

This module makes switching a single sequence with one lock, one set of
typed outcomes, and progress events at every step:

    PREPARING -> SIGNING_OUT -> WAITING_FOR_CLIENT -> AUTHENTICATING
              -> VERIFYING -> LAUNCHING -> DONE | FAILED

Sign-out is just the first half of that sequence, so the two operations can
no longer drift apart.
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
from utils.logger import Logger

#: League must be closed before the Riot Client will honour a sign-out.
GAME_PROCESSES = ("LeagueClient.exe", "LeagueClientUx.exe")

DEFAULT_SIGN_OUT_TIMEOUT_S = 12.0
DEFAULT_SIGN_IN_TIMEOUT_S = 25.0
DEFAULT_CLIENT_TIMEOUT_S = 30.0


class AccountSwitcher:
    """
    Runs account switches as one ordered, observable sequence.

    Deliberately owns no storage: the account list, credential decryption and
    persistence stay in AccountManager. This object only sequences the steps.
    """

    def __init__(
        self,
        session: RiotSession,
        accounts_provider: Callable[[], List[Dict[str, Any]]],
        password_provider: Callable[[int], str],
        on_success: Optional[Callable[[int], None]] = None,
        on_signed_out: Optional[Callable[[], None]] = None,
        kill_games: Optional[Callable[[], bool]] = None,
        launch_client: Optional[Callable[[], None]] = None,
        bus: Any = None,
        sign_out_timeout_s: float = DEFAULT_SIGN_OUT_TIMEOUT_S,
        client_timeout_s: float = DEFAULT_CLIENT_TIMEOUT_S,
    ):
        self.session = session
        self._accounts = accounts_provider
        self._password = password_provider
        self._on_success = on_success
        self._on_signed_out = on_signed_out
        self._kill_games = kill_games
        self._launch_client = launch_client
        self._bus = bus
        self._sign_out_timeout_s = sign_out_timeout_s
        self._client_timeout_s = client_timeout_s

        # ONE lock for every account operation. The old code had a
        # login-only flag that sign_out ignored, so you could sign out
        # halfway through a login.
        self._lock = threading.Lock()
        self._phase = SwitchPhase.IDLE
        self._current_label = ""

    # ------------------------------------------------------------- state
    @property
    def phase(self) -> SwitchPhase:
        return self._phase

    @property
    def busy(self) -> bool:
        return self._phase not in (SwitchPhase.IDLE, SwitchPhase.DONE, SwitchPhase.FAILED)

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
                "AccountSwitch",
                f"Could not publish '{channel}' — the interface will not be "
                f"told about this step.",
                exc=exc, channel=channel,
            )

    def _progress(self, phase: SwitchPhase, message: str, index: int = -1) -> None:
        self._phase = phase
        # The switch sequence is the flow that has never been observed against
        # a real Riot Client. A per-phase trail is the only way to see where
        # it stopped.
        Logger.info(
            "AccountSwitch",
            f"{getattr(phase, 'name', phase)}: {message}",
            phase=getattr(phase, "name", str(phase)),
            account_index=index,
        )
        self._emit(
            EVENT_SWITCH_PROGRESS,
            SwitchProgress(
                phase=phase,
                message=message,
                account_index=index,
                account_label=self._current_label,
            ),
        )

    def _finish(self, result: SwitchResult) -> SwitchResult:
        outcome = getattr(result.outcome, "name", str(result.outcome))
        operation = getattr(result, "operation", "switch")
        label = self._current_label or "account"
        if result.ok:
            Logger.action(
                "AccountSwitch",
                f"{operation} succeeded for {label}",
                outcome=outcome, operation=operation,
                account_index=getattr(result, "account_index", -1),
            )
        else:
            Logger.error(
                "AccountSwitch",
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

    # ----------------------------------------------------------- public API
    def switch_to(
        self,
        index: int,
        launch_league: bool = True,
        sign_in_timeout_s: float = DEFAULT_SIGN_IN_TIMEOUT_S,
    ) -> SwitchResult:
        """
        Switch to the account at `index`. Blocking; run it on a worker thread.

        Returns a typed SwitchResult in every case - it does not raise.
        """
        if not self._lock.acquire(blocking=False):
            return SwitchResult(SwitchOutcome.BUSY, SwitchPhase.IDLE, index)
        try:
            return self._switch_locked(index, launch_league, sign_in_timeout_s)
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
            self._emit(EVENT_SWITCH_STARTED, SwitchProgress(SwitchPhase.PREPARING, "Signing out"))
            outcome = self._ensure_signed_out()
            if outcome is not None:
                return self._finish(
                    SwitchResult(outcome, SwitchPhase.SIGNING_OUT, operation=OP_SIGN_OUT)
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
    def _switch_locked(
        self, index: int, launch_league: bool, sign_in_timeout_s: float
    ) -> SwitchResult:
        accounts = self._accounts() or []
        if not (0 <= index < len(accounts)):
            return self._finish(
                SwitchResult(SwitchOutcome.INVALID_ACCOUNT, SwitchPhase.PREPARING, index)
            )

        account = accounts[index]
        label = str(account.get("label") or account.get("username") or "Account")
        username = str(account.get("username") or "")
        self._current_label = label

        self._emit(
            EVENT_SWITCH_STARTED,
            SwitchProgress(SwitchPhase.PREPARING, "Switching to {}".format(label), index, label),
        )

        password = ""
        try:
            password = self._password(index) or ""
        except Exception:
            password = ""

        if not username or not password:
            return self._finish(
                SwitchResult(SwitchOutcome.NO_CREDENTIALS, SwitchPhase.PREPARING, index, label)
            )

        # --- 1. client reachable ------------------------------------------
        self._progress(SwitchPhase.WAITING_FOR_CLIENT, "Looking for the Riot Client", index)
        if not self.session.client_running():
            if self._launch_client:
                self._progress(SwitchPhase.WAITING_FOR_CLIENT, "Starting the Riot Client", index)
                try:
                    self._launch_client()
                except Exception as exc:
                    Logger.debug("Switcher", "_switch_locked suppressed an error", exc=exc)
            if not self.session.wait_until_client_ready(self._client_timeout_s):
                return self._finish(
                    SwitchResult(SwitchOutcome.CLIENT_NOT_RUNNING,
                                 SwitchPhase.WAITING_FOR_CLIENT, index, label)
                )
        elif not self.session.connect():
            return self._finish(
                SwitchResult(SwitchOutcome.CLIENT_UNREACHABLE,
                             SwitchPhase.WAITING_FOR_CLIENT, index, label)
            )

        # --- 2. already the right account? --------------------------------
        if self.session.is_signed_in():
            if username.lower() and self.session.current_login_name() == username.lower():
                if self._on_success:
                    try:
                        self._on_success(index)
                    except Exception as exc:
                        Logger.debug("Switcher", "_switch_locked suppressed an error", exc=exc)
                return self._finish(
                    SwitchResult(SwitchOutcome.ALREADY_ACTIVE, SwitchPhase.DONE, index, label)
                )

            # --- 3. sign the current account out --------------------------
            outcome = self._ensure_signed_out(index)
            if outcome is not None:
                return self._finish(SwitchResult(outcome, SwitchPhase.SIGNING_OUT, index, label))

        # --- 4. authenticate ----------------------------------------------
        self._progress(SwitchPhase.AUTHENTICATING, "Signing in as {}".format(label), index)
        attempt = self.session.sign_in(username, password)

        if attempt.needs_2fa:
            return self._finish(
                SwitchResult(SwitchOutcome.NEEDS_2FA, SwitchPhase.AUTHENTICATING,
                             index, label, attempt.error)
            )
        if not attempt.ok:
            return self._finish(
                SwitchResult(attempt.outcome, SwitchPhase.AUTHENTICATING,
                             index, label, attempt.error)
            )

        # --- 5. verify the client agrees -----------------------------------
        self._progress(SwitchPhase.VERIFYING, "Confirming sign-in", index)
        if not self.session.wait_until_signed_in(sign_in_timeout_s):
            return self._finish(
                SwitchResult(SwitchOutcome.TIMED_OUT, SwitchPhase.VERIFYING, index, label)
            )

        # --- 6. record + optionally launch ---------------------------------
        if self._on_success:
            try:
                self._on_success(index)
            except Exception as exc:
                Logger.debug("Switcher", "_switch_locked suppressed an error", exc=exc)

        if launch_league and self._launch_client:
            self._progress(SwitchPhase.LAUNCHING, "Starting League", index)
            try:
                self._launch_client()
            except Exception as exc:
                Logger.debug("Switcher", "_switch_locked suppressed an error", exc=exc)

        return self._finish(
            SwitchResult(SwitchOutcome.SUCCESS, SwitchPhase.DONE, index, label)
        )

    def _ensure_signed_out(self, index: int = -1) -> Optional[SwitchOutcome]:
        """
        Sign out whoever is signed in. Returns None on success, else why not.

        League must be closed first - the Riot Client refuses sign-out with
        `sign_out_failed_other_games_running` while it is up.
        """
        if not self.session.connect():
            return SwitchOutcome.CLIENT_UNREACHABLE

        if not self.session.is_signed_in():
            return None

        self._progress(SwitchPhase.SIGNING_OUT, "Closing League", index)
        if self._kill_games:
            try:
                self._kill_games()
            except Exception as exc:
                Logger.debug("Switcher", "_ensure_signed_out suppressed an error", exc=exc)

        self._progress(SwitchPhase.SIGNING_OUT, "Signing out", index)
        self.session.sign_out()

        # Verify rather than assuming, and rather than sleeping a fixed 2s.
        if not self.session.wait_until_signed_out(self._sign_out_timeout_s):
            return SwitchOutcome.SIGN_OUT_FAILED

        if self._on_signed_out:
            try:
                self._on_signed_out()
            except Exception as exc:
                Logger.debug("Switcher", "_ensure_signed_out suppressed an error", exc=exc)
        return None
