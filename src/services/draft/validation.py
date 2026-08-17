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
        """Collects all champions already picked or locked by either team."""
        picked = set()
        for member in session.get("myTeam", []):
            cid = member.get("championId", 0)
            if cid > 0:
                picked.add(int(cid))
        for member in session.get("theirTeam", []):
            cid = member.get("championId", 0)
            if cid > 0:
                picked.add(int(cid))

        # Also inspect completed pick actions
        for action_group in session.get("actions", []):
            for action in action_group:
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
