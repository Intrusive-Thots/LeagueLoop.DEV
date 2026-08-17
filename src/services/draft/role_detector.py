"""
Role and Position Detector for Champion Select.
Extracts assigned position and cell metadata from LCU Champ Select session payload.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class RoleDetector:
    """Detects player's assigned position in Champion Select."""

    ROLE_NORMALIZATION = {
        "top": "TOP",
        "jungle": "JUNGLE",
        "middle": "MIDDLE",
        "mid": "MIDDLE",
        "bottom": "BOTTOM",
        "bot": "BOTTOM",
        "utility": "UTILITY",
        "support": "UTILITY",
        "supp": "UTILITY",
    }

    @classmethod
    def normalize_role(cls, role: Optional[str]) -> str:
        """Normalizes Riot role strings to canonical names (TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY)."""
        if not role:
            return ""
        return cls.ROLE_NORMALIZATION.get(role.strip().lower(), role.strip().upper())

    @classmethod
    def get_local_cell_id(cls, session: Dict[str, Any]) -> int:
        """Finds local player cellId in champ select session."""
        return session.get("localPlayerCellId", -1)

    @classmethod
    def detect_role_from_session(cls, session: Dict[str, Any]) -> str:
        """
        Determines the assigned role for the local player.
        Checks myTeam cell assignedPosition first, then fallback session metadata.
        """
        local_cell_id = cls.get_local_cell_id(session)
        my_team = session.get("myTeam", [])

        for member in my_team:
            if member.get("cellId") == local_cell_id:
                raw_pos = member.get("assignedPosition", "")
                if raw_pos:
                    return cls.normalize_role(raw_pos)

        # Fallback: check session-level assignedPosition if present
        session_pos = session.get("assignedPosition", "")
        return cls.normalize_role(session_pos)
