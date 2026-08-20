"""
RiotSession — a typed, waitable view of the Riot Client's auth state.

Wraps the existing `RiotClientAPI` rather than replacing it, so the tested
HTTP/credential-discovery code stays in one place. What this adds is:

  * typed sign-in results instead of a raw response dict
  * `wait_until(...)` polling with a deadline, replacing the fixed
    `time.sleep(0.5)` / `sleep(2)` calls that made the old flow racy
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from services.accounts.results import RIOT_ERROR_MAP, SwitchOutcome

#: Poll interval when waiting for the client to change state.
POLL_INTERVAL_S = 0.4


@dataclass(frozen=True)
class AuthAttempt:
    """The result of one sign-in call."""

    outcome: SwitchOutcome
    raw_type: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.outcome is SwitchOutcome.SUCCESS

    @property
    def needs_2fa(self) -> bool:
        return self.outcome is SwitchOutcome.NEEDS_2FA


class RiotSession:
    """Typed operations against the local Riot Client."""

    def __init__(self, api: Any):
        self.api = api

    # ------------------------------------------------------------ liveness
    def client_running(self) -> bool:
        try:
            return bool(self.api.is_riot_client_running())
        except Exception:
            return False

    def connect(self) -> bool:
        try:
            return bool(self.api.connect())
        except Exception:
            return False

    @property
    def connected(self) -> bool:
        return bool(getattr(self.api, "is_connected", False))

    # ---------------------------------------------------------------- auth
    def is_signed_in(self) -> bool:
        try:
            return bool(self.api.is_signed_in())
        except Exception:
            return False

    def current_user(self) -> Optional[Dict[str, Any]]:
        try:
            return self.api.get_current_user()
        except Exception:
            return None

    def current_login_name(self) -> str:
        """The Riot login username currently signed in, lowercased."""
        info = self.current_user() or {}
        return str(info.get("preferred_username") or "").lower()

    def sign_in(self, username: str, password: str, persist: bool = False) -> AuthAttempt:
        """
        Sign in through the Riot Client API.

        This replaces typing credentials as keystrokes: the password goes
        straight to the local client over its authenticated API instead of
        into whatever window happens to hold focus.
        """
        try:
            body = self.api.sign_in(username, password, persist=persist) or {}
        except Exception as exc:
            return AuthAttempt(SwitchOutcome.ERROR, error=str(exc))

        auth_type = str(body.get("type") or "").lower()
        error = str(body.get("error") or "").lower()

        if auth_type == "multifactor":
            return AuthAttempt(SwitchOutcome.NEEDS_2FA, auth_type, error)

        if error:
            mapped = RIOT_ERROR_MAP.get(error)
            if mapped is None:
                # Don't guess "wrong password" from an unknown code.
                mapped = SwitchOutcome.ERROR
            return AuthAttempt(mapped, auth_type, error)

        if auth_type in ("success", "authenticated"):
            return AuthAttempt(SwitchOutcome.SUCCESS, auth_type)

        return AuthAttempt(SwitchOutcome.ERROR, auth_type, error or auth_type)

    def sign_out(self) -> bool:
        try:
            return bool(self.api.sign_out())
        except Exception:
            return False

    # -------------------------------------------------------------- waiting
    @staticmethod
    def wait_until(
        predicate: Callable[[], bool],
        timeout_s: float,
        interval_s: float = POLL_INTERVAL_S,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.monotonic,
    ) -> bool:
        """
        Poll `predicate` until it is true or the deadline passes.

        Used everywhere the old code slept a fixed amount and hoped. Returns
        True if the condition was met.
        """
        deadline = now() + max(0.0, timeout_s)
        while True:
            try:
                if predicate():
                    return True
            except Exception:
                pass
            if now() >= deadline:
                return False
            sleep(interval_s)

    def wait_until_signed_out(self, timeout_s: float = 12.0, **kw) -> bool:
        return self.wait_until(lambda: not self.is_signed_in(), timeout_s, **kw)

    def wait_until_signed_in(self, timeout_s: float = 20.0, **kw) -> bool:
        return self.wait_until(self.is_signed_in, timeout_s, **kw)

    def wait_until_client_ready(self, timeout_s: float = 30.0, **kw) -> bool:
        return self.wait_until(
            lambda: self.client_running() and self.connect(), timeout_s, **kw
        )
