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
    #: Save the session that is signed in right now, before replacing it.
    #: Without this, switching away from an account loses its session and the
    #: next switch back needs a manual sign-in.
    CAPTURING = "capturing"
    #: The Riot Client holds the session files open and rewrites them on exit,
    #: so it must be fully stopped before they are swapped.
    CLOSING_CLIENT = "closing_client"
    RESTORING_SESSION = "restoring_session"
    SIGNING_OUT = "signing_out"
    WAITING_FOR_CLIENT = "waiting_for_client"
    #: Signed out; waiting for the Riot sign-in form to be on screen.
    WAITING_FOR_SIGN_IN = "waiting_for_sign_in"
    #: Typing the stored username and password into that form.
    FILLING_FORM = "filling_form"
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
    #: Nothing has been captured for this account yet.
    NO_SAVED_SESSION = "no_saved_session"
    #: A session exists but is too old to be accepted. Restoring it would
    #: replace a possibly-good live session with a certainly-dead one.
    SESSION_EXPIRED = "session_expired"
    #: The Riot Client would not stop, so the files cannot be swapped safely.
    CLIENT_STILL_RUNNING = "client_still_running"
    #: The Riot sign-in window never appeared after signing out.
    LOGIN_FORM_NOT_FOUND = "login_form_not_found"
    #: Focus kept moving away from the Riot Client while typing.
    FOCUS_LOST = "focus_lost"
    #: Riot showed an hCaptcha and it was not solved in time.
    CAPTCHA_REQUIRED = "captcha_required"
    #: The client signed in, but as a different Riot account.
    WRONG_ACCOUNT = "wrong_account"
    #: The Riot Client is on the right account but League opened on another
    #: one (stale product tokens), and a full Riot restart did not fix it.
    LEAGUE_WRONG_ACCOUNT = "league_wrong_account"
    #: League started but never finished logging in, even after restarting
    #: League and then the Riot Client (seen live: Riot's login queue
    #: rejected the token with "Invalid JTI claim").
    LEAGUE_LOGIN_FAILED = "league_login_failed"
    ERROR = "error"


#: Outcomes where retrying the same action could plausibly work.
RETRYABLE = frozenset({
    SwitchOutcome.CLIENT_UNREACHABLE,
    SwitchOutcome.TIMED_OUT,
    SwitchOutcome.SIGN_OUT_FAILED,
    SwitchOutcome.CLIENT_STILL_RUNNING,
    SwitchOutcome.LOGIN_FORM_NOT_FOUND,
    SwitchOutcome.FOCUS_LOST,
    SwitchOutcome.LEAGUE_WRONG_ACCOUNT,
    SwitchOutcome.LEAGUE_LOGIN_FAILED,
    SwitchOutcome.ERROR,
})

#: Outcomes that only a human can clear. Retrying these is a spinner that
#: never ends, so the UI offers the remedy instead of a Try Again button.
NEEDS_MANUAL_SIGN_IN = frozenset({
    SwitchOutcome.NO_SAVED_SESSION,
    SwitchOutcome.SESSION_EXPIRED,
    SwitchOutcome.NEEDS_2FA,
    SwitchOutcome.CAPTCHA_REQUIRED,
})

#: Human sentences, in product vocabulary (UI/UX Master Plan §55, §56).
#: Every one says what happened and, where relevant, what to do next.
OUTCOME_MESSAGES = {
    SwitchOutcome.SUCCESS: "Signed in.",
    SwitchOutcome.ALREADY_ACTIVE: "That account is already signed in.",
    SwitchOutcome.NEEDS_2FA: (
        "Riot asked for a two-factor code. Enter it in the Riot Client by hand "
        "to finish signing in."
    ),
    SwitchOutcome.BAD_CREDENTIALS: "Riot rejected the username or password for this account.",
    SwitchOutcome.RATE_LIMITED: "Riot is rate limiting sign-in attempts. Wait a moment and try again.",
    SwitchOutcome.CLIENT_NOT_RUNNING: "The Riot Client is not running.",
    SwitchOutcome.CLIENT_UNREACHABLE: "Could not reach the Riot Client.",
    SwitchOutcome.SIGN_OUT_FAILED: "Could not sign out the current account.",
    SwitchOutcome.TIMED_OUT: "Timed out waiting for the Riot Client.",
    SwitchOutcome.BUSY: "Another account operation is already running.",
    SwitchOutcome.INVALID_ACCOUNT: "That account no longer exists.",
    SwitchOutcome.NO_CREDENTIALS: (
        "This account has no saved password. Press Edit on it and enter the "
        "password, then press Switch again."
    ),
    SwitchOutcome.NO_SAVED_SESSION: (
        "No saved session for this account. Sign in to it once by hand and "
        "LeagueLoop will remember it."
    ),
    SwitchOutcome.SESSION_EXPIRED: (
        "This account's saved session has expired. Sign in to it once by "
        "hand to refresh it."
    ),
    SwitchOutcome.CLIENT_STILL_RUNNING: (
        "The Riot Client would not close, so the account was left as it was."
    ),
    SwitchOutcome.LOGIN_FORM_NOT_FOUND: (
        "Signed out, but the Riot sign-in window did not appear. Open the Riot "
        "Client and press Switch again."
    ),
    SwitchOutcome.FOCUS_LOST: (
        "Could not keep the Riot Client in front long enough to type the "
        "sign-in. Don't click other windows while it types, then press Switch "
        "again."
    ),
    SwitchOutcome.CAPTCHA_REQUIRED: (
        "Riot is asking for a captcha. Solve it in the Riot Client by hand "
        "and the sign-in will finish."
    ),
    SwitchOutcome.WRONG_ACCOUNT: (
        "The Riot Client signed in to a different account than the one "
        "selected. Check this account's username."
    ),
    SwitchOutcome.LEAGUE_WRONG_ACCOUNT: (
        "The Riot Client is on the right account, but League opened on a "
        "different one, even after restarting the Riot Client. Close League "
        "and the Riot Client, then press Switch again."
    ),
    SwitchOutcome.LEAGUE_LOGIN_FAILED: (
        "The Riot Client signed in, but League couldn't finish logging in, "
        "even after restarting League and the Riot Client. Close both, open "
        "the Riot Client, check you're signed in, then press Play."
    ),
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
    "multifactor": SwitchOutcome.NEEDS_2FA,
    "captcha": SwitchOutcome.CAPTCHA_REQUIRED,
    "invalid_prompt": SwitchOutcome.CAPTCHA_REQUIRED,
}

#: Outcomes whose `detail` is a user-facing sentence worth appending.
DETAILED_OUTCOMES = frozenset({
    SwitchOutcome.TIMED_OUT,
    SwitchOutcome.SIGN_OUT_FAILED,
    SwitchOutcome.LOGIN_FORM_NOT_FOUND,
    SwitchOutcome.WRONG_ACCOUNT,
})


# Which operation produced a result. SUCCESS means two different things
# depending on it - "you are signed in" vs "you are signed out" - and a
# sign-out that announces "Signed in." is worse than no message at all.
OP_SWITCH = "switch"
OP_SIGN_OUT = "sign_out"


@dataclass(frozen=True)
class SwitchResult:
    """The outcome of one account switch or sign-out."""

    outcome: SwitchOutcome
    phase: SwitchPhase = SwitchPhase.DONE
    account_index: int = -1
    account_label: str = ""
    detail: str = ""
    operation: str = OP_SWITCH
    #: After a successful switch: did League start? None = not asked / can't tell.
    league_started: Optional[bool] = None
    #: Is League signed in as the same account as the Riot Client?
    #: True = checked and equal; None = not checked / League still loading.
    league_account_ok: Optional[bool] = None
    #: League started but had not finished logging in when we stopped waiting.
    league_login_pending: bool = False

    @property
    def ok(self) -> bool:
        return self.outcome in (SwitchOutcome.SUCCESS, SwitchOutcome.ALREADY_ACTIVE)

    @property
    def retryable(self) -> bool:
        return self.outcome in RETRYABLE

    @property
    def message(self) -> str:
        base = OUTCOME_MESSAGES.get(self.outcome, OUTCOME_MESSAGES[SwitchOutcome.ERROR])
        if self.outcome is SwitchOutcome.SUCCESS:
            if self.operation == OP_SIGN_OUT:
                return "Signed out."
            if self.account_label:
                if self.league_started is False:
                    return ("Signed in as {}, but League didn't start - press Play "
                            "in the Riot Client.".format(self.account_label))
                if self.league_started and self.league_login_pending:
                    return ("Signed in as {}. League is still loading - if it "
                            "stays stuck, close it and press Play.".format(self.account_label))
                return "Signed in as {}.".format(self.account_label)
        if self.outcome is SwitchOutcome.ALREADY_ACTIVE and self.league_started is False:
            return base + " League didn't start - press Play in the Riot Client."
        if self.detail and self.outcome in DETAILED_OUTCOMES:
            return "{} {}".format(base, self.detail)
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
