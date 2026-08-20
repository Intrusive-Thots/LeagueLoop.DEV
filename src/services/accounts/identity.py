"""
Who is signed in, and which stored account is that?

Detection used to be ~150 lines inlined in `AccountManager`, mixing four
concerns: reading two different APIs, matching names, mutating the account
list, and fetching the wallet. It also wrote `_active_idx` and called
`_save()` from a background thread without taking the lock, which made it a
second source of truth racing the switcher.

The parts that need testing - reading an identity out of an API payload, and
deciding which stored account it corresponds to - are pure functions here.
Storage and locking stay in `AccountManager`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


class MatchKind(Enum):
    """How a match was reached. Weaker kinds are guesses, and say so."""

    #: Stored login username == the client's login username. Exact.
    LOGIN_USERNAME = "login_username"
    #: Stored Riot ID == the client's Riot ID. Exact.
    RIOT_ID = "riot_id"
    #: Stored label happens to equal the in-game name. A guess.
    LABEL_GUESS = "label_guess"
    #: Nobody matched.
    NONE = "none"


#: Kinds we are willing to treat as fact. A label collision must not silently
#: repoint the active account.
CONFIDENT = (MatchKind.LOGIN_USERNAME, MatchKind.RIOT_ID)


@dataclass(frozen=True)
class ClientIdentity:
    """
    The signed-in identity as the client reports it.

    Normalises on construction rather than trusting callers to lowercase, so
    the case-insensitivity of every comparison downstream is a property of the
    type instead of a convention someone has to remember.
    """

    login_name: str = ""
    game_name: str = ""
    tag_line: str = ""

    def __post_init__(self) -> None:
        for field in ("login_name", "game_name", "tag_line"):
            object.__setattr__(self, field, _lower(getattr(self, field)))

    @property
    def riot_id(self) -> str:
        if self.game_name and self.tag_line:
            return "{}#{}".format(self.game_name, self.tag_line)
        return self.game_name

    @property
    def is_empty(self) -> bool:
        return not (self.login_name or self.game_name)

    def display_name(self) -> str:
        """Something a human can read, preferring the in-game name."""
        return self.riot_id or self.login_name or "Unknown account"


def from_riot_userinfo(payload: Optional[Dict[str, Any]]) -> ClientIdentity:
    """Parse `GET /riot-client-auth/v1/userinfo`."""
    if not payload:
        return ClientIdentity()
    acct = payload.get("acct") or {}
    return ClientIdentity(
        login_name=_lower(payload.get("preferred_username")),
        game_name=_lower(acct.get("game_name")),
        tag_line=_lower(acct.get("tag_line")),
    )


def from_lcu_summoner(payload: Optional[Dict[str, Any]]) -> ClientIdentity:
    """
    Parse `GET /lol-summoner/v1/current-summoner`.

    The LCU knows the in-game name but never the Riot login username, so an
    identity from here can only ever match on Riot ID.
    """
    if not payload:
        return ClientIdentity()
    return ClientIdentity(
        game_name=_lower(payload.get("gameName")),
        tag_line=_lower(payload.get("tagLine")),
    )


@dataclass(frozen=True)
class AccountMatch:
    """Which stored account the identity corresponds to, and how sure we are."""

    index: int = -1
    kind: MatchKind = MatchKind.NONE

    @property
    def found(self) -> bool:
        return self.index >= 0

    @property
    def confident(self) -> bool:
        return self.found and self.kind in CONFIDENT


def match_account(
    identity: ClientIdentity, accounts: Sequence[Dict[str, Any]]
) -> AccountMatch:
    """
    Find the stored account for a signed-in identity.

    Rules run strongest-first and the whole list is checked at each strength
    before dropping to a weaker one. The original did the opposite - it fell
    through to a label guess on the *first* account before trying an exact
    Riot ID match on the second.
    """
    if identity.is_empty or not accounts:
        return AccountMatch()

    if identity.login_name:
        for i, acct in enumerate(accounts):
            if _lower(acct.get("username")) == identity.login_name:
                return AccountMatch(i, MatchKind.LOGIN_USERNAME)

    riot_id = identity.riot_id
    if riot_id:
        for i, acct in enumerate(accounts):
            if _lower(acct.get("tagline")) == riot_id:
                return AccountMatch(i, MatchKind.RIOT_ID)

    if identity.game_name:
        for i, acct in enumerate(accounts):
            if _lower(acct.get("label")) == identity.game_name:
                return AccountMatch(i, MatchKind.LABEL_GUESS)

    return AccountMatch()


def missing_tagline_update(
    identity: ClientIdentity, account: Optional[Dict[str, Any]]
) -> str:
    """
    The Riot ID to fill in for a matched account that has none, or "".

    Only ever fills a *blank* field. The old code applied the live Riot ID to
    whatever `_active_idx` pointed at, without checking that the index had
    anything to do with the identity it had just read - so signing into an
    unrecognised account could rewrite a different account's Riot ID.
    """
    if account is None or not identity.riot_id:
        return ""
    if _lower(account.get("tagline")):
        return ""
    return identity.riot_id
