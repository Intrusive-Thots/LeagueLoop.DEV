"""
Champion Priority Decision Engine for LeagueLoop Draft Automation.
Computes deterministic champion choices based on assigned roles, priority ranks,
availability constraints, and backup cascades.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from services.draft.role_detector import RoleDetector
from services.draft.validation import ActionValidator


@dataclass(frozen=True)
class DraftEvaluationResult:
    """Outcome of a draft priority evaluation."""
    action_type: str  # "pick" or "ban"
    champion_id: int
    score: float
    role: str
    is_fallback: bool
    reason: str


class PriorityEngine:
    """
    Evaluates Champion Select session state against user-configured priorities.
    Applies role matching, availability filtering, and conflict penalty resolution.
    """

    def __init__(self, config_manager=None, asset_manager=None):
        self.config = config_manager
        self.assets = asset_manager

    def evaluate_pick(
        self,
        session: Dict[str, Any],
        custom_priorities: Optional[List[int]] = None,
    ) -> Optional[DraftEvaluationResult]:
        """
        Determines the best available champion to pick.
        Evaluates role-specific priority list first, then general list, then fallbacks.
        """
        role = RoleDetector.detect_role_from_session(session)
        priority_list = custom_priorities or self._get_pick_priorities_for_role(role)

        if not priority_list:
            return None

        for rank_idx, champ_id in enumerate(priority_list):
            if ActionValidator.is_champion_available(champ_id, session, is_pick=True):
                # Calculate deterministic score
                priority_weight = max(100.0 - (rank_idx * 10.0), 10.0)
                role_match_bonus = 20.0 if self._is_champion_valid_for_role(champ_id, role) else 0.0
                total_score = priority_weight + role_match_bonus

                return DraftEvaluationResult(
                    action_type="pick",
                    champion_id=champ_id,
                    score=total_score,
                    role=role,
                    is_fallback=(rank_idx > 0),
                    reason=f"Priority rank #{rank_idx + 1} for role '{role}'" if role else f"Priority rank #{rank_idx + 1}",
                )

        return None

    def evaluate_ban(
        self,
        session: Dict[str, Any],
        custom_bans: Optional[List[int]] = None,
    ) -> Optional[DraftEvaluationResult]:
        """
        Determines the best available champion to ban.
        Evaluates configured ban priority list against current banned state.
        """
        role = RoleDetector.detect_role_from_session(session)
        ban_list = custom_bans or self._get_ban_priorities_for_role(role)

        if not ban_list:
            return None

        for rank_idx, champ_id in enumerate(ban_list):
            if ActionValidator.is_champion_available(champ_id, session, is_pick=False):
                ban_weight = max(100.0 - (rank_idx * 10.0), 10.0)
                return DraftEvaluationResult(
                    action_type="ban",
                    champion_id=champ_id,
                    score=ban_weight,
                    role=role,
                    is_fallback=(rank_idx > 0),
                    reason=f"Ban priority rank #{rank_idx + 1}",
                )

        return None

    def _get_pick_priorities_for_role(self, role: str) -> List[int]:
        """Reads priority list for the role from config, fallback to default priority."""
        if not self.config:
            return []

        # Role-specific priority key e.g. "priority_TOP", "priority_MIDDLE"
        role_key = f"priority_{role}" if role else "priority_list"
        raw_list = self.config.get(role_key, [])
        if not raw_list and role:
            # Fallback to general priority_list
            raw_list = self.config.get("priority_list", [])

        # Ensure integers
        result = []
        for item in raw_list:
            try:
                result.append(int(item))
            except (ValueError, TypeError):
                continue
        return result

    def _get_ban_priorities_for_role(self, role: str) -> List[int]:
        """Reads ban list from config."""
        if not self.config:
            return []

        raw_list = self.config.get(f"ban_priority_{role}", []) if role else []
        if not raw_list:
            raw_list = self.config.get("ban_priority", [])

        result = []
        for item in raw_list:
            try:
                result.append(int(item))
            except (ValueError, TypeError):
                continue
        return result

    def _is_champion_valid_for_role(self, champ_id: int, role: str) -> bool:
        """Checks if champion is canonically played in this role via AssetManager metadata."""
        if not role or not self.assets:
            return True
        roles = self.assets.get_champ_roles(champ_id) if hasattr(self.assets, "get_champ_roles") else ()
        return role.upper() in [r.upper() for r in roles] if roles else True
