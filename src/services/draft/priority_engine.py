"""
Champion Priority Decision Engine for LeagueLoop Draft Automation.
Computes deterministic champion choices based on assigned roles, priority ranks,
availability constraints, and backup cascades.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.config_keys import (
    ARAM_PRIORITY_LIST,
    BAN_LIST,
    PRIORITY_LIST,
    read_champion_ids,
    role_ban_key,
    role_priority_key,
)

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
    #: Zero-based position in the list this came from. The view model was
    #: deriving confidence from a hardcoded `0 if not is_fallback else 1`,
    #: which made `Confidence.LOW` unreachable and turned a three-value badge
    #: into a two-value fallback flag.
    rank: int = 0
    #: Which list was actually consulted. The recommendation came from the
    #: role or ARAM list while the backups beside it came from the global
    #: one, so the two rows could disagree.
    source_list: Tuple[int, ...] = ()


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
        aram: Optional[bool] = None,
        rejected_ids: Optional[Any] = None,
    ) -> Optional[DraftEvaluationResult]:
        """
        Determines the best available champion to pick.

        Order: caller override, then the ARAM list when this is ARAM, then the
        role-specific list, then the general list.

        `aram` is inferred from the session's queue id when not passed, so
        callers that do not know or care still get the right list.
        """
        role = RoleDetector.detect_role_from_session(session)
        if aram is None:
            aram = self._is_aram(session)
        priority_list = custom_priorities or self._get_pick_priorities_for_role(
            role, aram=aram
        )

        if not priority_list:
            return None

        rejected_set = set(rejected_ids) if rejected_ids else set()

        for rank_idx, champ_id in enumerate(priority_list):
            if champ_id in rejected_set:
                continue
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
                    rank=rank_idx,
                    source_list=tuple(priority_list),
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

    @staticmethod
    def _is_aram(session: Dict[str, Any]) -> bool:
        """
        ARAM by queue id, from the session the client gave us.

        450 is ARAM; 720 is ARAM Clash. Unknown queues are treated as not
        ARAM, so an unrecognised mode falls back to the general list rather
        than picking nothing.
        """
        for candidate in (
            (session or {}).get("queueId"),
            ((session or {}).get("gameConfig") or {}).get("queueId"),
        ):
            try:
                if int(candidate) in (450, 720):
                    return True
            except (TypeError, ValueError):
                continue
        return False

    def _get_pick_priorities_for_role(self, role: str, aram: bool = False) -> List[int]:
        """
        Pick priorities: role-specific, else the general list.

        Key names come from `core.config_keys` because this used to read a
        literal that the UI did not write.
        """
        if not self.config:
            return []

        if aram:
            aram_list = read_champion_ids(self.config, ARAM_PRIORITY_LIST, asset_manager=self.assets)
            if aram_list:
                return aram_list
            # Fallback to legacy priority_picker list if configured
            legacy = self.config.get("priority_picker", {})
            if isinstance(legacy, dict) and legacy.get("list"):
                legacy_list = read_champion_ids({"_legacy": legacy.get("list", [])}, "_legacy", asset_manager=self.assets)
                if legacy_list:
                    return legacy_list

        if role:
            role_list = read_champion_ids(self.config, role_priority_key(role), asset_manager=self.assets)
            if role_list:
                return role_list

        main_list = read_champion_ids(self.config, PRIORITY_LIST, asset_manager=self.assets)
        if main_list:
            return main_list

        # Fallback to legacy priority_picker list
        legacy = self.config.get("priority_picker", {})
        if isinstance(legacy, dict) and legacy.get("list"):
            legacy_list = read_champion_ids({"_legacy": legacy.get("list", [])}, "_legacy", asset_manager=self.assets)
            if legacy_list:
                return legacy_list

        return []

    def _get_ban_priorities_for_role(self, role: str) -> List[int]:
        """
        Ban priorities: role-specific, else the list the Bans screen writes.

        This read `ban_priority`, which nothing has ever written. The Bans
        screen writes `ban_list`, so every configured ban was ignored.
        """
        if not self.config:
            return []

        if role:
            role_list = read_champion_ids(self.config, role_ban_key(role), asset_manager=self.assets)
            if role_list:
                return role_list

        return read_champion_ids(self.config, BAN_LIST, asset_manager=self.assets)


    def _is_champion_valid_for_role(self, champ_id: int, role: str) -> bool:
        """Checks if champion is canonically played in this role via AssetManager metadata."""
        if not role or not self.assets:
            return True
        roles = self.assets.get_champ_roles(champ_id) if hasattr(self.assets, "get_champ_roles") else ()
        return role.upper() in [r.upper() for r in roles] if roles else True
