"""
AccountSwitcher - switch accounts the way a person does it.

    PREPARING            the account exists and has a username + saved password
    LAUNCHING            start the Riot Client if it is not running
    SIGNING_OUT          close League, sign the current account out (API)
    WAITING_FOR_SIGN_IN  wait for the Riot sign-in form to be on screen
    FILLING_FORM         type USERNAME, PASSWORD, press Enter (form_login.py)
    VERIFYING            wait for Riot to accept it: 2FA, captcha, wrong
                         password and rate limits are reported as such
    LAUNCHING            start League, if asked
    DONE | FAILED

History, so nobody re-adds the dead ends:

* POSTing the password to the client's `rso-authenticator` API is refused
  with `invalid_prompt` - it carries an hCaptcha the API cannot solve.
* Restoring copied session files does not work: unless "Stay signed in" was
  ticked the client keeps no reusable session, so every restore landed on
  the sign-in screen ("Confirming the account" -> SESSION_EXPIRED).

Typing into the on-screen form is the one path Riot accepts; if Riot shows a
captcha there, the user solves it in the client and this sequence keeps
waiting for it.

The password is read from the encrypted store only for the moment it is
typed. It is never logged, never part of a progress message or a result.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

from services.accounts.form_login import FillStatus, RiotFormFiller
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

TAG = "AccountSwitch"

GAME_PROCESSES = ("LeagueClient.exe", "LeagueClientUx.exe")
CLIENT_PROCESS = "RiotClientServices.exe"

DEFAULT_SIGN_OUT_TIMEOUT_S = 12.0
DEFAULT_CLIENT_TIMEOUT_S = 30.0
#: How long to wait for the sign-in window after signing out. If it has not
#: appeared after `REOPEN_AFTER_S`, the Riot Client is launched once more,
#: which brings its window up when it was running in the tray.
DEFAULT_SIGN_IN_SCREEN_TIMEOUT_S = 30.0
REOPEN_AFTER_S = 8.0
#: How long to wait for Riot to accept the submitted form. Long on purpose:
#: a captcha or a 2FA code is solved by a person in this window.
DEFAULT_VERIFY_TIMEOUT_S = 120.0
#: With no answer after this long, tell the user what to look for.
NUDGE_AFTER_S = 8.0
POLL_S = 0.5


class AccountSwitcher:
    """Runs account switches as one ordered, observable sequence."""

    def __init__(
        self,
        session: RiotSession,
        accounts_provider: Callable[[], List[Dict[str, Any]]],
        password_provider: Optional[Callable[[int], str]] = None,
        form_filler: Optional[RiotFormFiller] = None,
        on_success: Optional[Callable[[int], None]] = None,
        on_signed_out: Optional[Callable[[], None]] = None,
        kill_games: Optional[Callable[[], bool]] = None,
        client_running: Optional[Callable[[], bool]] = None,
        launch_client: Optional[Callable[[bool], None]] = None,
        bus: Any = None,
        sign_out_timeout_s: float = DEFAULT_SIGN_OUT_TIMEOUT_S,
        client_timeout_s: float = DEFAULT_CLIENT_TIMEOUT_S,
        sign_in_screen_timeout_s: float = DEFAULT_SIGN_IN_SCREEN_TIMEOUT_S,
        verify_timeout_s: float = DEFAULT_VERIFY_TIMEOUT_S,
        nudge_after_s: float = NUDGE_AFTER_S,
        reopen_after_s: float = REOPEN_AFTER_S,
        poll_s: float = POLL_S,
        vault: Any = None,
        **_legacy: Any,
    ):
        self.session = session
        self._accounts = accounts_provider
        self._password = password_provider
        self.form = form_filler if form_filler is not None else RiotFormFiller()
        #: Kept only for diagnostics (`check_accounts`); switching ignores it.
        self.vault = vault
        self._on_success = on_success
        self._on_signed_out = on_signed_out
        self._kill_games = kill_games
        self._client_running = client_running
        self._launch_client = launch_client
        self._bus = bus
        self._sign_out_timeout_s = sign_out_timeout_s
        self._client_timeout_s = client_timeout_s
        self._sign_in_screen_timeout_s = sign_in_screen_timeout_s
        self._verify_timeout_s = verify_timeout_s
        self._nudge_after_s = nudge_after_s
        self._reopen_after_s = reopen_after_s
        self._poll_s = poll_s

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
            Logger.error(
                TAG,
                f"Could not publish '{channel}' - the interface will not be "
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
        label = self._current_label or getattr(result, "account_label", "") or "account"
        if result.ok:
            Logger.action(
                TAG, f"{operation} succeeded for {label}",
                outcome=outcome, operation=operation,
                account_index=getattr(result, "account_index", -1),
            )
        else:
            is_benign = result.outcome in (
                SwitchOutcome.SESSION_EXPIRED, SwitchOutcome.CLIENT_NOT_RUNNING,
                SwitchOutcome.NEEDS_2FA, SwitchOutcome.CAPTCHA_REQUIRED,
            )
            log_fn = Logger.warning if is_benign else Logger.error
            detail_str = f" - {result.detail}" if getattr(result, "detail", "") else ""
            log_fn(
                TAG,
                f"{operation} failed for {label}: {outcome}{detail_str}",
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
        """The Riot login name, lowercased - what `preferred_username` says."""
        return str(account.get("username") or account.get("label") or "").strip().lower()

    # ----------------------------------------------------------- public API
    def session_info(self, index: int):
        """Legacy diagnostics only: what the old session vault holds."""
        accounts = self._accounts() or []
        if self.vault is None or not (0 <= index < len(accounts)):
            return None
        return self.vault.info(self.account_key(accounts[index]))

    def capture_current(self, index: int) -> bool:
        """Legacy diagnostics only. Switching does not use saved sessions."""
        accounts = self._accounts() or []
        if self.vault is None or not (0 <= index < len(accounts)):
            return False
        return self.vault.capture(self.account_key(accounts[index]))

    def switch_to(self, index: int, launch_league: bool = True) -> SwitchResult:
        """Switch to the account at `index`. Blocking; run on a worker thread."""
        if not self._lock.acquire(blocking=False):
            return SwitchResult(SwitchOutcome.BUSY, SwitchPhase.IDLE, index)
        try:
            return self._switch_locked(index, launch_league)
        except Exception as exc:
            # Type name only - never risk echoing anything that was typed.
            return self._finish(
                SwitchResult(
                    SwitchOutcome.ERROR, self._phase, index,
                    self._current_label, type(exc).__name__,
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
            return self._finish(
                SwitchResult(
                    SwitchOutcome.SUCCESS, SwitchPhase.DONE, operation=OP_SIGN_OUT
                )
            )
        except Exception as exc:
            return self._finish(
                SwitchResult(
                    SwitchOutcome.ERROR, self._phase,
                    detail=type(exc).__name__, operation=OP_SIGN_OUT,
                )
            )
        finally:
            self._lock.release()

    # ------------------------------------------------------------ sequence
    def _fail(self, outcome, phase, index, label, detail="") -> SwitchResult:
        return self._finish(SwitchResult(outcome, phase, index, label, detail))

    def _switch_locked(self, index: int, launch_league: bool) -> SwitchResult:
        accounts = self._accounts() or []
        if not (0 <= index < len(accounts)):
            return self._finish(
                SwitchResult(SwitchOutcome.INVALID_ACCOUNT, SwitchPhase.PREPARING, index)
            )

        account = accounts[index]
        label = str(account.get("label") or account.get("username") or "Account")
        username = str(account.get("username") or "").strip()
        key = username.lower()
        self._current_label = label

        self._emit(
            EVENT_SWITCH_STARTED,
            SwitchProgress(SwitchPhase.PREPARING, "Switching to {}".format(label), index, label),
        )

        # --- 1. can this switch work at all? Checked before anything closes.
        if not username or not self._has_password(index):
            return self._fail(SwitchOutcome.NO_CREDENTIALS, SwitchPhase.PREPARING, index, label)
        if not self.form.available():
            return self._fail(
                SwitchOutcome.ERROR, SwitchPhase.PREPARING, index, label,
                "Typing into the Riot Client is only possible on Windows.",
            )

        # --- 2. make sure the Riot Client is up ---------------------------
        if not self._client_is_running():
            self._progress(SwitchPhase.LAUNCHING, "Starting the Riot Client", index)
            if self._launch_client:
                self._safely(self._launch_client, False)
            self._progress(SwitchPhase.WAITING_FOR_CLIENT, "Waiting for the Riot Client to start", index)
            if not self.session.wait_until_client_ready(self._client_timeout_s):
                return self._fail(SwitchOutcome.CLIENT_NOT_RUNNING, SwitchPhase.WAITING_FOR_CLIENT, index, label)

        # --- 3. already there? ---------------------------------------------
        if self._already_active(key):
            if self._on_success:
                self._safely(self._on_success, index)
            if launch_league:
                self._progress(SwitchPhase.LAUNCHING, "Launching League of Legends", index)
                self.session.launch_league()
            return self._finish(
                SwitchResult(SwitchOutcome.ALREADY_ACTIVE, SwitchPhase.DONE, index, label)
            )

        # --- 4. sign the current account out ---------------------------------
        outcome = self._ensure_signed_out(index)
        if outcome is not None:
            return self._fail(outcome, SwitchPhase.SIGNING_OUT, index, label)

        # --- 5. wait for the sign-in form -----------------------------------
        self._progress(SwitchPhase.WAITING_FOR_SIGN_IN, "Waiting for the Riot sign-in screen", index)
        if not self._wait_for_sign_in_screen():
            return self._fail(SwitchOutcome.LOGIN_FORM_NOT_FOUND, SwitchPhase.WAITING_FOR_SIGN_IN, index, label)

        # --- 6. type and submit ----------------------------------------------
        self._progress(
            SwitchPhase.FILLING_FORM,
            "Typing {}'s username and password - don't click other windows "
            "for a few seconds".format(label),
            index,
        )
        pre_state = self.session.auth_state()
        password = self._read_password(index)
        try:
            fill = self.form.fill_and_submit(
                username, password,
                on_step=lambda msg: self._progress(SwitchPhase.FILLING_FORM, msg, index),
            )
        finally:
            password = ""  # drop our reference as soon as it is typed
        if not fill.ok:
            mapping = {
                FillStatus.WINDOW_NOT_FOUND: SwitchOutcome.LOGIN_FORM_NOT_FOUND,
                FillStatus.FOCUS_FAILED: SwitchOutcome.FOCUS_LOST,
                FillStatus.FOCUS_LOST: SwitchOutcome.FOCUS_LOST,
            }
            return self._fail(
                mapping.get(fill.status, SwitchOutcome.ERROR),
                SwitchPhase.FILLING_FORM, index, label, fill.detail,
            )

        # --- 7. did Riot accept it? ---------------------------------------------
        self._progress(SwitchPhase.VERIFYING, "Submitted - waiting for Riot to sign in {}".format(label), index)
        verdict = self._wait_for_sign_in(key, pre_state, index)
        if verdict is not None:
            outcome, detail = verdict
            return self._fail(outcome, SwitchPhase.VERIFYING, index, label, detail)

        if self._on_success:
            self._safely(self._on_success, index)
        if launch_league:
            self._progress(SwitchPhase.LAUNCHING, "Signed in - launching League of Legends", index)
            self.session.launch_league()
        return self._finish(SwitchResult(SwitchOutcome.SUCCESS, SwitchPhase.DONE, index, label))

    # ------------------------------------------------------------- helpers
    def _has_password(self, index: int) -> bool:
        return bool(self._read_password(index))

    def _read_password(self, index: int) -> str:
        if self._password is None:
            return ""
        try:
            return str(self._password(index) or "")
        except Exception:
            return ""

    def _client_is_running(self) -> bool:
        if self._client_running is None:
            return self.session.client_running()
        try:
            return bool(self._client_running())
        except Exception:
            return False

    def _already_active(self, key: str) -> bool:
        if not key:
            return False
        try:
            if not self.session.connect() or not self.session.is_signed_in():
                return False
            return self.session.current_login_name() == key
        except Exception as exc:
            Logger.debug(TAG, "Could not read the current account", exc=exc)
            return False

    def _wait_for_sign_in_screen(self) -> bool:
        """Signed out, and the Riot Client window is on screen."""
        start = time.monotonic()
        deadline = start + self._sign_in_screen_timeout_s
        reopened = False
        while True:
            hwnd = self.form.wait_for_window(timeout_s=0)
            if hwnd and not self.session.is_signed_in():
                ready = self.form.form_ready(hwnd)
                # None: UI Automation cannot look; trust the window + settle.
                if ready is None or ready:
                    return True
            now = time.monotonic()
            if not hwnd and not reopened and now - start >= self._reopen_after_s and self._launch_client:
                # Running in the tray with no window: launching it again
                # brings the window up.
                reopened = True
                Logger.info(TAG, "No Riot Client window yet; asking it to open")
                self._safely(self._launch_client, False)
            if now >= deadline:
                return False
            time.sleep(self._poll_s)

    def _wait_for_sign_in(self, key: str, pre_state, index: int):
        """None when signed in as `key`; else (outcome, detail)."""
        start = time.monotonic()
        deadline = start + self._verify_timeout_s
        told_captcha = told_2fa = nudged = False
        pre_kind = RiotSession.classify_auth_state(pre_state)
        while True:
            if self.session.is_signed_in():
                current = self.session.current_login_name()
                if current and key and current != key:
                    return (SwitchOutcome.WRONG_ACCOUNT, "")
                return None

            state = self.session.auth_state()
            kind = RiotSession.classify_auth_state(state)
            if state == pre_state and kind == pre_kind and kind in ("auth_failure", "rate_limited", "captcha"):
                kind = ""  # a leftover from before this attempt
            if kind == "auth_failure":
                return (SwitchOutcome.BAD_CREDENTIALS, "")
            if kind == "rate_limited":
                return (SwitchOutcome.RATE_LIMITED, "")
            if kind == "multifactor" and not told_2fa:
                told_2fa = True
                self._progress(
                    SwitchPhase.VERIFYING,
                    "Riot wants a two-factor code - enter it in the Riot "
                    "Client. LeagueLoop is still waiting.",
                    index,
                )
            captcha = kind == "captcha" or self.form.captcha_visible() is True
            if captcha and not told_captcha:
                told_captcha = True
                self._progress(
                    SwitchPhase.VERIFYING,
                    "Riot is showing a captcha - solve it in the Riot Client. "
                    "LeagueLoop is still waiting.",
                    index,
                )

            now = time.monotonic()
            if not nudged and not told_captcha and not told_2fa and now - start >= self._nudge_after_s:
                nudged = True
                self._progress(
                    SwitchPhase.VERIFYING,
                    "Still waiting for Riot. If a captcha is showing, solve it "
                    "in the Riot Client. If the username or password box is "
                    "empty, press Switch again.",
                    index,
                )
            if now >= deadline:
                if told_2fa:
                    return (SwitchOutcome.NEEDS_2FA, "")
                if told_captcha:
                    return (SwitchOutcome.CAPTCHA_REQUIRED, "")
                return (
                    SwitchOutcome.TIMED_OUT,
                    "Riot never confirmed the sign-in. Look at the Riot Client: "
                    "if the boxes are empty, press Switch again.",
                )
            time.sleep(self._poll_s)

    def _ensure_signed_out(self, index: int = -1) -> Optional[SwitchOutcome]:
        """Sign out whoever is signed in. Returns None on success, else why not.

        League must be closed first - the Riot Client refuses sign-out with
        `sign_out_failed_other_games_running` while it is up.
        """
        if not self.session.connect():
            return SwitchOutcome.CLIENT_UNREACHABLE

        if not self.session.is_signed_in():
            return None

        current = ""
        try:
            current = self.session.current_login_name()
        except Exception:
            current = ""

        self._progress(SwitchPhase.SIGNING_OUT, "Closing League", index)
        if self._kill_games:
            self._safely(self._kill_games)

        self._progress(
            SwitchPhase.SIGNING_OUT,
            "Signing out {}".format(current) if current else "Signing out",
            index,
        )
        self.session.sign_out()
        if not self.session.wait_until_signed_out(self._sign_out_timeout_s):
            # One retry: League can take a moment to release the client.
            if self._kill_games:
                self._safely(self._kill_games)
            self.session.sign_out()
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
