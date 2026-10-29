"""One-line champ-select status for the sidebar header: whose turn, and time left.

The header used to say "● Drafting" for the whole draft, with no turn and no
clock. Built from `ChampSelectState` (live session, aged timer) so it reads
the same data the engine acts on. Shapes captured from a live Ranked Solo/Duo
draft (tests/fixtures/lcu/champ_select_ranked_*.json): bans live only in
`actions` (`session.bans` stays empty in ranked), picks go in pairs with
several actions `isInProgress` at once, and the local cell may sit on either
side (cell 6 here).
"""
from __future__ import annotations

import time
from typing import Any, Iterable, Optional, Tuple


def _my_side_cells(state: Any) -> set:
    cells = set()
    for p in getattr(state, "my_team", ()) or ():
        try:
            cells.add(int(p.get("cellId")))
        except (TypeError, ValueError, AttributeError):
            continue
    return cells


def time_left_s(state: Any, now: Optional[float] = None) -> float:
    """Seconds left, counted down from when the state was published."""
    left = float(getattr(state, "timer_remaining_s", 0.0) or 0.0)
    sampled = float(getattr(state, "timer_sampled_at", 0.0) or 0.0)
    if sampled > 0:
        age = (time.time() if now is None else now) - sampled
        if 0 < age < 600:
            left -= age
    return max(0.0, left)


def turn_label(state: Any) -> str:
    """Whose turn it is, in a few words."""
    phase = str(getattr(state, "timer_phase", "") or "").upper()
    if phase == "PLANNING":
        return "Declare intent"
    if phase == "FINALIZATION":
        return "Finalizing"
    if phase == "GAME_STARTING":
        return "Game starting"

    my_cell = getattr(state, "cell_id", -1)
    allies = _my_side_cells(state)
    live = [a for a in (getattr(state, "actions", ()) or ())
            if isinstance(a, dict) and a.get("isInProgress") and not a.get("completed")]
    if not live:
        return "Locked in" if getattr(state, "locked_in", False) else "Drafting"

    if any(a.get("type") == "ten_bans_reveal" for a in live):
        return "Bans revealed"
    mine = [a for a in live if a.get("actorCellId") == my_cell]
    if mine:
        return "Your ban" if mine[0].get("type") == "ban" else "Your pick"
    kind = "ban" if any(a.get("type") == "ban" for a in live) else "pick"
    if kind == "ban":
        return "Bans"
    if any(a.get("actorCellId") in allies for a in live):
        return "Team picking"
    return "Enemy picking"


def draft_status(state: Any, now: Optional[float] = None) -> Tuple[str, bool]:
    """("● Your pick · 0:18", is_my_turn)."""
    label = turn_label(state)
    secs = int(round(time_left_s(state, now)))
    text = f"● {label}"
    if secs > 0 and label not in ("Game starting",):
        text += f" · {secs // 60}:{secs % 60:02d}"
    return text, label in ("Your ban", "Your pick")
