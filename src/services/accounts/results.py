"""
Typed results and events for account switching.

The previous implementation reported everything as free-text through a
`log_func` callback, so callers could not tell "wrong password" from "the
client isn't running" from "we timed out" without string matching. These are
the outcomes an account switch can actually have, plus the events the UI
listens to.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

# --- EventBus channel names -------------------------------------------------
# Defined here rather than in core.events so the accounts subsystem can add
# events without changing the shared enum.
EVENT_SWITCH_STARTED = "account_switch_started"
EVENT_SWITCH_PROGRESS = "account_switch_progress"
EVENT_SWITCH_FINISHED = "account_switch_finished"


class SwitchPhase(Enum):
    """Where a switch has got to. Emitted with every progress event."""

    IDLE = "idle"
    PREPARING = "preparing"
    SIGNING_OUT = "signing_out"
    WAITING_FOR_CLIENT = "waiting_for_client"
    AUTHENTICATING = "authenticating"
    VERIFYING = "verifying"
    LAUNCHING = "launching"
    DONE = "done"
    FAILED = "failed"


class SwitchOutcome(Enum):
    """
    Why a switch ended.

    Split into distinct cases deliberately: the UI shows a different message
    (and a different next action) for each, which a boolean cannot express.
    """

    SUCCESS = "success"
    ALREADY_ACTIVE = "already_active"
    NEEDS_2FA = "needs_2fa"
    BAD_CREDENTIALS = "bad_credentials"
    RATE_LIMITED = "rate_limited"
    CLIENT_NOT_RUNNING = "client_not_running"
    CLIENT_UNREACHABLE = "client_unreachable"
    SIGN_OUT_FAILED = "sign_out_failed"
    TIMED_OUT = "timed_out"
    BUSY = "busy"
    INVALID_ACCOUNT = "invalid_account"
    NO_CREDENTIALS = "no_credentials"
    ERROR = "error"


#: Outcomes where retrying the same action could plausibly work.
RETRYABLE = frozenset({
    SwitchOutcome.CLIENT_UNREACHABLE,
    SwitchOutcome.TIMED_OUT,
    SwitchOutcome.SIGN_OUT_FAILED,
    SwitchOutcome.ERROR,
})

#: Human sentences, in product vocabulary (UI/UX Master Plan §55, §56).
#: Every one says what happened and, where relevant, what to do next.
OUTCOME_MESSAGES = {
    SwitchOutcome.SUCCESS: "Signed in.",
    SwitchOutcome.ALREADY_ACTIVE: "That account is already signed in.",
    SwitchOutcome.NEEDS_2FA: "Two-factor code required - finish signing in in the Riot Client.",
    SwitchOutcome.BAD_CREDENTIALS: "Riot rejected the username or password for this account.",
    SwitchOutcome.RATE_LIMITED: "Riot is rate limiting sign-in attempts. Wait a moment and try again.",
    SwitchOutcome.CLIENT_NOT_RUNNING: "The Riot Client is not running.",
    SwitchOutcome.CLIENT_UNREACHABLE: "Could not reach the Riot Client.",
    SwitchOutcome.SIGN_OUT_FAILED: "Could not sign out the current account.",
    SwitchOutcome.TIMED_OUT: "Timed out waiting for the Riot Client.",
    SwitchOutcome.BUSY: "Another account operation is already running.",
    SwitchOutcome.INVALID_ACCOUNT: "That account no longer exists.",
    SwitchOutcome.NO_CREDENTIALS: "This account has no saved password.",
    SwitchOutcome.ERROR: "Account switch failed.",
}

#: Riot error codes -> outcomes. Anything unmapped falls back to BAD_CREDENTIALS
#: only when Riot explicitly reported an auth failure, never by guessing.
RIOT_ERROR_MAP = {
    "auth_failure": SwitchOutcome.BAD_CREDENTIALS,
    "invalid_credentials": SwitchOutcome.BAD_CREDENTIALS,
    "credentials_invalid": SwitchOutcome.BAD_CREDENTIALS,
    "rate_limited": SwitchOutcome.RATE_LIMITED,
    "too_many_attempts": SwitchOutcome.RATE_LIMITED,
}


@dataclass(frozen=True)
class SwitchResult:
    """The outcome of one account switch."""

    outcome: SwitchOutcome
    phase: SwitchPhase = SwitchPhase.DONE
    account_index: int = -1
    account_label: str = ""
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.outcome in (SwitchOutcome.SUCCESS, SwitchOutcome.ALREADY_ACTIVE)

    @property
    def retryable(self) -> bool:
        return self.outcome in RETRYABLE

    @property
    def message(self) -> str:
        base = OUTCOME_MESSAGES.get(self.outcome, OUTCOME_MESSAGES[SwitchOutcome.ERROR])
        if self.account_label and self.outcome is SwitchOutcome.SUCCESS:
            return "Signed in as {}.".format(self.account_label)
        return base

    def __str__(self) -> str:
        return "{} ({})".format(self.message, self.outcome.value)


@dataclass(frozen=True)
class SwitchProgress:
    """A step along the way, for the activity feed and status line."""

    phase: SwitchPhase
    message: str
    account_index: int = -1
    account_label: str = ""
