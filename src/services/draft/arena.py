"""Who your Arena teammates are, read from a champ-select session.

Arena lobbies don't look like 5v5 drafts. A live Bravery Arena draft (queue
1740, gameMode CHERRY; tests/fixtures/lcu/champ_select_arena_bravery_*.json)
put all 18 players in `myTeam` with `team: 1`, left `theirTeam` empty, and ran
every pick at once. Your own trio (cells 9-11 there) are the only rows whose
spells, pick intent and champion the client shows; the other subteams read as
zeros. "First other cell in myTeam" was therefore a hidden stranger, never the
partner. A champion id of -3 is the Bravery placeholder, not a champion.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from core.constants import ARENA_QUEUES

ARENA_GAME_MODE = "CHERRY"


def is_arena(queue_id: Any = None, game_mode: Any = None) -> bool:
    try:
        if int(queue_id) in ARENA_QUEUES:
            return True
    except (TypeError, ValueError):
        pass
    return str(game_mode or "").upper() == ARENA_GAME_MODE


def champion_of(player: Mapping[str, Any]) -> int:
    """Locked champion, else hover intent; 0 for none or a placeholder (<0)."""
    for key in ("championId", "championPickIntent"):
        try:
            cid = int(player.get(key) or 0)
        except (TypeError, ValueError):
            cid = 0
        if cid > 0:
            return cid
    return 0


def _visible(player: Mapping[str, Any]) -> bool:
    return bool(
        player.get("spell1Id") or player.get("spell2Id")
        or player.get("championId") or player.get("championPickIntent")
    )


def teammates(session: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Your Arena teammates (partner, or both trio-mates), excluding you."""
    me_cell = session.get("localPlayerCellId")
    my_team = [p for p in (session.get("myTeam") or []) if isinstance(p, dict)]
    others = [p for p in my_team if p.get("cellId") != me_cell]
    if session.get("theirTeam"):
        # Old 2v2 shape: myTeam is just your side.
        return others
    if len(my_team) <= 3:
        return others
    return [p for p in others if _visible(p)]


def partner_target(session: Mapping[str, Any], pair_names: Optional[set] = None,
                   name_of=None) -> Optional[Dict[str, Any]]:
    """The teammate to build synergy around.

    Prefers a teammate whose champion has a configured pair, then any teammate
    with a champion, then the first teammate.
    """
    mates = teammates(session)
    if not mates:
        return None
    if pair_names and name_of is not None:
        for p in mates:
            cid = champion_of(p)
            if cid and (name_of(cid) or "").lower() in pair_names:
                return p
    for p in mates:
        if champion_of(p):
            return p
    return mates[0]
