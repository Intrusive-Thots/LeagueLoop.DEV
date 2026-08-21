"""
Draft Action Validation for Champion Select.
Ensures champions selected or banned are valid, available, and not picked or banned by other players.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set


class ActionValidator:
    """Validates champion selection and banning availability."""

    @staticmethod
    def get_banned_champion_ids(session: Dict[str, Any]) -> Set[int]:
        """Collects all banned champion IDs across both teams."""
        banned = set()
        bans = session.get("bans", {})
        for my_ban in bans.get("myTeamBans", []):
            if my_ban:
                banned.add(int(my_ban))
        for their_ban in bans.get("theirTeamBans", []):
            if their_ban:
                banned.add(int(their_ban))

        # Inspect session bannedChampions list
        for b in session.get("bannedChampions", []):
            if isinstance(b, dict):
                cid = b.get("championId", 0)
                if cid:
                    banned.add(int(cid))
            elif b:
                try:
                    banned.add(int(b))
                except (TypeError, ValueError):
                    pass

        # Also inspect completed ban actions in session actions matrix
        for action_group in session.get("actions", []):
            for action in action_group:
                if action.get("type") == "ban" and action.get("completed", False):
                    cid = action.get("championId", 0)
                    if cid > 0:
                        banned.add(int(cid))
        return banned

    @staticmethod
    def get_picked_champion_ids(session: Dict[str, Any]) -> Set[int]:
        """
        Champions taken by *someone else*.

        The local player's own cell is excluded. This counted your own hover
        as unavailable, so the moment anything selected your top priority the
        engine decided it was taken: the on-screen recommendation flipped to
        your second choice, and auto-pick hovered a champion it then refused
        to lock in because it believed someone had it.
        """
        picked = set()
        try:
            my_cell = int(session.get("localPlayerCellId", -1))
        except (TypeError, ValueError):
            my_cell = -1

        for member in session.get("myTeam", []):
            if member.get("cellId") == my_cell and my_cell >= 0:
                continue
            cid = member.get("championId", 0)
            if cid > 0:
                picked.add(int(cid))
            intent = member.get("championPickIntent", 0)
            if intent > 0:
                picked.add(int(intent))
        for member in session.get("theirTeam", []):
            cid = member.get("championId", 0)
            if cid > 0:
                picked.add(int(cid))

        # Also inspect completed pick actions — again, not your own.
        for action_group in session.get("actions", []):
            for action in action_group:
                if action.get("actorCellId") == my_cell and my_cell >= 0:
                    continue
                if action.get("type") == "pick" and action.get("completed", False):
                    cid = action.get("championId", 0)
                    if cid > 0:
                        picked.add(int(cid))
        return picked

    @classmethod
    def is_champion_available(
        cls,
        champion_id: int,
        session: Dict[str, Any],
        is_pick: bool = True,
    ) -> bool:
        """
        Returns True if champion_id is legal to pick or ban.
        - Picks cannot choose banned champions or already picked champions.
        - Bans cannot choose already banned champions.
        """
        if champion_id <= 0:
            return False

        banned = cls.get_banned_champion_ids(session)
        if champion_id in banned:
            return False

        if is_pick:
            picked = cls.get_picked_champion_ids(session)
            if champion_id in picked:
                return False

        return True
