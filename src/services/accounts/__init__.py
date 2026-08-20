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
    OUTCOME_MESSAGES,
    SwitchOutcome,
    SwitchPhase,
    SwitchProgress,
    SwitchResult,
)
from services.accounts.session import AuthAttempt, RiotSession
from services.accounts.switcher import AccountSwitcher

__all__ = [
    "AccountSwitcher",
    "RiotSession",
    "AuthAttempt",
    "SwitchResult",
    "SwitchProgress",
    "SwitchOutcome",
    "SwitchPhase",
    "OUTCOME_MESSAGES",
    "EVENT_SWITCH_STARTED",
    "EVENT_SWITCH_PROGRESS",
    "EVENT_SWITCH_FINISHED",
]
