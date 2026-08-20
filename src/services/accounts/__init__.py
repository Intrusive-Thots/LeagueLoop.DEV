"""
Account switching subsystem.

Sequencing lives in `AccountSwitcher`, the typed view of the Riot Client in
`RiotSession`, and the outcome vocabulary in `results`. Storage, encryption
and the account list stay in `services.account_manager`.
"""
from services.accounts.results import (
    EVENT_SWITCH_FINISHED,
    EVENT_SWITCH_PROGRESS,
    EVENT_SWITCH_STARTED,
    OP_SIGN_OUT,
    OP_SWITCH,
    OUTCOME_MESSAGES,
    SwitchOutcome,
    SwitchPhase,
    SwitchProgress,
    SwitchResult,
)
from services.accounts.identity import (
    AccountMatch,
    ClientIdentity,
    MatchKind,
    from_lcu_summoner,
    from_riot_userinfo,
    match_account,
    missing_tagline_update,
)
from services.accounts.session import AuthAttempt, RiotSession
from services.accounts.switcher import AccountSwitcher

__all__ = [
    "AccountSwitcher",
    "ClientIdentity",
    "AccountMatch",
    "MatchKind",
    "from_riot_userinfo",
    "from_lcu_summoner",
    "match_account",
    "missing_tagline_update",
    "RiotSession",
    "AuthAttempt",
    "SwitchResult",
    "SwitchProgress",
    "SwitchOutcome",
    "SwitchPhase",
    "OUTCOME_MESSAGES",
    "OP_SWITCH",
    "OP_SIGN_OUT",
    "EVENT_SWITCH_STARTED",
    "EVENT_SWITCH_PROGRESS",
    "EVENT_SWITCH_FINISHED",
]
