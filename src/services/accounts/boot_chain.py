"""
Everything that must be true between switching the PC on and standing in a game.

Written from a search of how the Riot stack actually behaves in 2026, because
the account switcher kept failing at a *different* step each time and the code
had no way to name which one. Each stage below is a real precondition with a
real observable, so "it didn't work" becomes "stage 4 of 9, and here is why".

The chain
---------
::

    1  BOOT              Windows starts; the vgc service starts Vanguard
    2  VANGUARD          vgk.sys is loaded in the kernel
    3  RIOT_CLIENT       RiotClientServices.exe running, local API reachable
    4  SESSION           an authenticated Riot session exists
    5  LAUNCH_LEAGUE     --launch-product=league_of_legends --launch-patchline=live
    6  LEAGUE_CLIENT     LeagueClientUx.exe running, LCU lockfile written
    7  LOGGED_IN         /lol-login/v1/session reports SUCCEEDED
    8  LOBBY_TO_DRAFT    gameflow: Lobby -> Matchmaking -> ReadyCheck -> ChampSelect
    9  IN_GAME           "League of Legends.exe" running; gameflow InProgress

Why each one matters, and what it cost us
-----------------------------------------
**Vanguard (1-2).** League will not launch unless Vanguard's kernel driver is
loaded, and the driver only loads at boot. Starting the vgc service by hand
after Windows is up is not enough — Riot's own error text for this asks for a
restart. So a switcher that force-closes and relaunches everything can still
end at a wall that only rebooting clears. Worth naming rather than retrying.

**Session (4) is the one that broke us.** Riot's credential sign-in now
carries an hCaptcha challenge: the local `rso-authenticator` flow expects a
solved captcha token, and without one it answers `invalid_prompt` — which is
exactly the error this project chased through three separate implementations.
Public tooling that still logs in with a password either drives a captcha
solving service or types the password into the client window with synthetic
keystrokes. Riot's own documentation recommends the third option instead:
**reuse the stored session cookie rather than sending the password again.**
That is what `vault.py` does, and it is why this switcher no longer has a
password path at all.

**Sessions expire.** Refreshing with the `ssid` cookie alone is reliable for
about a week; keeping the whole cookie set stretches it to about three. After
that the client shows a login screen no automation can get past. A switcher
that cannot tell a fresh session from a stale one looks broken at exactly the
moment it matters, so `Stage.SESSION` reports age, not just presence.

Nothing here drives anything. It is a description of the world that the
switcher and the UI both read, so they cannot disagree about where a switch
got to.

Sources are recorded in `claude/Account_Switching_Rewrite.md`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class Stage(Enum):
    """One link in the chain from power-on to in-game."""

    BOOT = "boot"
    VANGUARD = "vanguard"
    RIOT_CLIENT = "riot_client"
    SESSION = "session"
    LAUNCH_LEAGUE = "launch_league"
    LEAGUE_CLIENT = "league_client"
    LOGGED_IN = "logged_in"
    LOBBY_TO_DRAFT = "lobby_to_draft"
    IN_GAME = "in_game"


#: The order they must happen in. Index is the stage number the UI shows.
ORDER: List[Stage] = [
    Stage.BOOT,
    Stage.VANGUARD,
    Stage.RIOT_CLIENT,
    Stage.SESSION,
    Stage.LAUNCH_LEAGUE,
    Stage.LEAGUE_CLIENT,
    Stage.LOGGED_IN,
    Stage.LOBBY_TO_DRAFT,
    Stage.IN_GAME,
]


@dataclass(frozen=True)
class StageSpec:
    """What a stage means, how to observe it, and what to do when it is not met."""

    stage: Stage
    #: One line, in product vocabulary, for the UI.
    title: str
    #: How this stage is checked. Names a process, a file or an endpoint —
    #: never "it should work by now".
    observable: str
    #: What the user (or the app) can do when this stage is the blocker.
    remedy: str
    #: True when nothing the application does can satisfy it.
    needs_human: bool = False


SPECS = {
    Stage.BOOT: StageSpec(
        Stage.BOOT,
        "Windows has started",
        "the session exists at all",
        "Nothing to do.",
    ),
    Stage.VANGUARD: StageSpec(
        Stage.VANGUARD,
        "Vanguard is loaded",
        "the vgc service is running and vgk.sys is loaded",
        "Vanguard's driver only loads during boot. If it is not loaded, "
        "restart the PC — starting the service by hand is not enough.",
        needs_human=True,
    ),
    Stage.RIOT_CLIENT: StageSpec(
        Stage.RIOT_CLIENT,
        "The Riot Client is running",
        "RiotClientServices.exe, plus its lockfile in "
        r"%LOCALAPPDATA%\Riot Games\Riot Client\Config",
        "Launch the Riot Client.",
    ),
    Stage.SESSION: StageSpec(
        Stage.SESSION,
        "A Riot account is signed in",
        "the saved session files for this account, and their age",
        "Restore this account's saved session, or sign in once by hand so "
        "the session can be captured.",
    ),
    Stage.LAUNCH_LEAGUE: StageSpec(
        Stage.LAUNCH_LEAGUE,
        "League has been asked to start",
        "RiotClientServices.exe launched with "
        "--launch-product=league_of_legends --launch-patchline=live",
        "Ask the Riot Client to launch League.",
    ),
    Stage.LEAGUE_CLIENT: StageSpec(
        Stage.LEAGUE_CLIENT,
        "The League Client is up",
        "LeagueClientUx.exe, and a readable LCU lockfile",
        "Wait for the client to finish starting, or patch if it is patching.",
    ),
    Stage.LOGGED_IN: StageSpec(
        Stage.LOGGED_IN,
        "The League Client has finished signing in",
        "/lol-login/v1/session reports state SUCCEEDED",
        "Wait. If it stays pending, the session was not accepted and the "
        "account needs a manual sign-in.",
    ),
    Stage.LOBBY_TO_DRAFT: StageSpec(
        Stage.LOBBY_TO_DRAFT,
        "In a lobby or a draft",
        "/lol-gameflow/v1/gameflow-phase",
        "Pick a queue and start matchmaking.",
    ),
    Stage.IN_GAME: StageSpec(
        Stage.IN_GAME,
        "In game",
        '"League of Legends.exe" running, gameflow phase InProgress',
        "Nothing to do.",
    ),
}

#: Gameflow phases, in the order the client moves through them. Used to place
#: a live phase string on the chain rather than matching it by hand in
#: several files.
GAMEFLOW_ORDER = (
    "None",
    "Lobby",
    "Matchmaking",
    "ReadyCheck",
    "ChampSelect",
    "GameStart",
    "InProgress",
    "WaitingForStats",
    "PreEndOfGame",
    "EndOfGame",
)

#: Phases that mean the draft has begun or passed.
_DRAFT_OR_LATER = ("ChampSelect", "GameStart", "InProgress")


def stage_for_phase(phase: str) -> Optional[Stage]:
    """Where a gameflow phase sits on the chain.

    Returns None for a phase we do not place, rather than guessing — an
    unknown phase from a future patch must not be reported as in-game.
    """
    if not phase:
        return None
    if phase in ("InProgress", "GameStart"):
        return Stage.IN_GAME
    if phase in ("Lobby", "Matchmaking", "ReadyCheck", "ChampSelect"):
        return Stage.LOBBY_TO_DRAFT
    if phase in GAMEFLOW_ORDER:
        return Stage.LOGGED_IN
    return None


@dataclass(frozen=True)
class StageStatus:
    """Whether one stage is satisfied, and what was seen."""

    stage: Stage
    met: bool
    detail: str = ""

    @property
    def spec(self) -> StageSpec:
        return SPECS[self.stage]


@dataclass(frozen=True)
class ChainStatus:
    """The whole chain, evaluated once."""

    stages: List[StageStatus]

    @property
    def blocker(self) -> Optional[StageStatus]:
        """The first unmet stage — the only one worth telling the user about.

        Reporting every unmet stage is noise: stages after the blocker are
        unmet *because* of it, not independently.
        """
        for status in self.stages:
            if not status.met:
                return status
        return None

    @property
    def ready_to_play(self) -> bool:
        return self.blocker is None

    @property
    def reached(self) -> int:
        """How many stages are satisfied, for a progress readout."""
        for index, status in enumerate(self.stages):
            if not status.met:
                return index
        return len(self.stages)

    def summary(self) -> str:
        """One sentence naming where things stand."""
        blocker = self.blocker
        if blocker is None:
            return "Ready to play."
        return "Step {} of {}: {} — {}".format(
            self.reached + 1, len(self.stages),
            blocker.spec.title,
            blocker.detail or blocker.spec.remedy,
        )


__all__ = [
    "ChainStatus", "GAMEFLOW_ORDER", "ORDER", "SPECS", "Stage", "StageSpec",
    "StageStatus", "stage_for_phase",
]
