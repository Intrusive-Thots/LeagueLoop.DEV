"""
ChampSelectViewModel — presentation state for the draft screen
(UI/UX Master Plan §11-§16).

Turns `core.state.ChampSelectState` plus the existing
`services.draft.PriorityEngine` into things a view can render directly:
a recommendation, its reasons, ranked backups, and what automation intends
to do next.

Deliberately no fake precision (§14): confidence is High / Medium / Low /
Blocked, never "97.42%".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from core.state import ApplicationState, ChampSelectState, GameflowPhase


class Confidence(Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    BLOCKED = "Blocked"


@dataclass
class Recommendation:
    """What LeagueLoop suggests picking, and why (§14)."""

    champion_id: int = 0
    name: str = ""
    key: str = ""
    confidence: Confidence = Confidence.BLOCKED
    reasons: List[str] = field(default_factory=list)
    is_fallback: bool = False
    winrate: Optional[float] = None  # Lolalytics winrate %

    @property
    def valid(self) -> bool:
        return self.champion_id > 0


#: Draft phases shown on the timeline, in order.
TIMELINE_PHASES = ("READY", "ROLE", "PICK", "BAN", "CONFIRM")

ROLE_LABELS = {
    "TOP": "Top",
    "JUNGLE": "Jungle",
    "MIDDLE": "Mid",
    "BOTTOM": "ADC",
    "UTILITY": "Support",
    "": "Unassigned",
}


class ChampSelectViewModel(QObject):
    """Presentation state for the Champ Select screen."""

    changed = Signal()

    def __init__(self, container: Any = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._container = container
        self._state: ChampSelectState = ChampSelectState()
        self._app_state: ApplicationState = ApplicationState()
        self._recommendation = Recommendation()
        self._backups: List[Recommendation] = []

        self._engine = None
        try:
            from services.draft import PriorityEngine  # type: ignore

            self._engine = PriorityEngine(
                config_manager=getattr(container, "config", None),
                asset_manager=getattr(container, "assets", None),
            )
        except Exception:
            self._engine = None

    # --------------------------------------------------------------- input
    def apply(self, app_state: ApplicationState) -> None:
        """Adopt a new application state snapshot and recompute."""
        self._app_state = app_state
        self._state = app_state.champ_select
        self._recompute()
        self.changed.emit()

    # -------------------------------------------------------------- getters
    @property
    def state(self) -> ChampSelectState:
        return self._state

    @property
    def active(self) -> bool:
        return bool(
            self._state.active
            or self._app_state.client.phase == GameflowPhase.CHAMP_SELECT.value
        )

    @property
    def role_label(self) -> str:
        role = (self._state.local_role or "").upper()
        return ROLE_LABELS.get(role, role.title() or "Unassigned")

    @property
    def remaining_s(self) -> float:
        return max(0.0, float(self._state.timer_remaining_s or 0.0))

    @property
    def recommendation(self) -> Recommendation:
        return self._recommendation

    @property
    def backups(self) -> List[Recommendation]:
        return list(self._backups)

    @property
    def locked_in(self) -> bool:
        return bool(self._state.locked_in)

    def timeline_index(self) -> int:
        """Which timeline step to highlight (§12)."""
        if not self.active:
            return 0
        if self._state.locked_in:
            return TIMELINE_PHASES.index("CONFIRM")
        if not self._state.local_role:
            return TIMELINE_PHASES.index("ROLE")
        for action in self._state.actions or ():
            if isinstance(action, dict) and action.get("isInProgress"):
                if str(action.get("type", "")).lower() == "ban":
                    return TIMELINE_PHASES.index("BAN")
                return TIMELINE_PHASES.index("PICK")
        return TIMELINE_PHASES.index("PICK")

    def timer_label(self) -> str:
        """Contextual caption for the countdown (§13)."""
        if self._state.locked_in:
            return "Locked in"
        step = TIMELINE_PHASES[self.timeline_index()]
        return {"BAN": "Ban now", "PICK": "Select now", "CONFIRM": "Confirm"}.get(
            step, "Waiting"
        )

    def automation_summary(self) -> str:
        """One line describing the next automated action (§2.5, §15)."""
        auto = self._app_state.automation
        if not auto.running:
            return "Automation is off - you are picking manually."
        if auto.paused:
            return "Automation is paused."
        if self._state.locked_in:
            return "Champion locked in."
        if self._recommendation.valid:
            return "Will select {}.".format(self._recommendation.name)
        return "No eligible champion in your priority list."

    # ------------------------------------------------------------ internals
    def _session_dict(self) -> Dict[str, Any]:
        """Rebuild the LCU-shaped session the draft services expect."""
        return {
            "localPlayerCellId": self._state.cell_id,
            "myTeam": list(self._state.my_team or ()),
            "theirTeam": list(self._state.their_team or ()),
            "actions": [list(self._state.actions or ())],
        }

    def _champ_name(self, champ_id: int) -> str:
        assets = getattr(self._container, "assets", None)
        getter = getattr(assets, "get_champ_name", None)
        if callable(getter):
            try:
                return getter(champ_id) or str(champ_id)
            except Exception:
                pass
        return str(champ_id)

    def _champ_key(self, champ_id: int) -> str:
        assets = getattr(self._container, "assets", None)
        mapping = getattr(assets, "id_to_key", None)
        if isinstance(mapping, dict):
            return str(mapping.get(champ_id, ""))
        return ""

    @staticmethod
    def _confidence_for(rank: int, is_fallback: bool, role_matched: bool) -> Confidence:
        """
        Coarse confidence buckets (§14 forbids fake precision).

        Top of the list and the right role reads High; a fallback deeper in
        the list reads Medium; anything further down reads Low.
        """
        if rank == 0 and role_matched:
            return Confidence.HIGH
        if rank <= 2:
            return Confidence.MEDIUM if is_fallback or not role_matched else Confidence.HIGH
        return Confidence.LOW

    def _recompute(self) -> None:
        self._recommendation = Recommendation()
        self._backups = []

        if not self.active or self._engine is None:
            return

        session = self._session_dict()
        try:
            result = self._engine.evaluate_pick(session)
        except Exception:
            result = None

        if result is None:
            self._recommendation = Recommendation(
                confidence=Confidence.BLOCKED,
                reasons=["No available champion matches your priority list"],
            )
            return

        role = (result.role or "").upper()
        role_matched = True
        assets = getattr(self._container, "assets", None)
        getter = getattr(assets, "get_champ_roles", None)
        if role and callable(getter):
            try:
                roles = getter(result.champion_id) or []
                role_matched = not roles or role in [str(r).upper() for r in roles]
            except Exception:
                role_matched = True

        name = self._champ_name(result.champion_id)
        scraper = getattr(self._container, "scraper", None)
        wr = scraper.get_winrate(name) if scraper else None

        reasons = []
        if wr is not None:
            reasons.append(f"{wr:.1f}% WR (Lolalytics)")
        reasons.append(result.reason)
        if role:
            reasons.append("{} selected".format(ROLE_LABELS.get(role, role.title())))
        reasons.append("Available")
        if result.is_fallback:
            reasons.append("Earlier priorities unavailable")

        self._recommendation = Recommendation(
            champion_id=result.champion_id,
            name=name,
            key=self._champ_key(result.champion_id),
            confidence=self._confidence_for(0 if not result.is_fallback else 1,
                                            result.is_fallback, role_matched),
            reasons=reasons,
            is_fallback=result.is_fallback,
            winrate=wr,
        )

        self._backups = self._compute_backups(session, result.champion_id)

    def _compute_backups(
        self, session: Dict[str, Any], chosen_id: int, limit: int = 4
    ) -> List[Recommendation]:
        """Next available priorities after the recommended one (§14)."""
        backups: List[Recommendation] = []
        config = getattr(self._container, "config", None)
        if config is None:
            return backups

        try:
            raw = config.get("priority_list", []) or []
        except Exception:
            return backups

        try:
            from services.draft import ActionValidator  # type: ignore
        except Exception:
            ActionValidator = None  # type: ignore

        scraper = getattr(self._container, "scraper", None)

        for champ_id in raw:
            try:
                cid = int(champ_id)
            except (TypeError, ValueError):
                continue
            if cid == chosen_id:
                continue
            if ActionValidator is not None:
                try:
                    if not ActionValidator.is_champion_available(cid, session, is_pick=True):
                        continue
                except Exception:
                    pass
            b_name = self._champ_name(cid)
            b_wr = scraper.get_winrate(b_name) if scraper else None
            b_reasons = ["Backup"]
            if b_wr is not None:
                b_reasons.append(f"{b_wr:.1f}% WR")
            backups.append(
                Recommendation(
                    champion_id=cid,
                    name=b_name,
                    key=self._champ_key(cid),
                    confidence=Confidence.MEDIUM,
                    reasons=b_reasons,
                    winrate=b_wr,
                )
            )
            if len(backups) >= limit:
                break
        return backups
