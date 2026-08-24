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
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from core.state import ApplicationState, ChampSelectState, GameflowPhase
from utils.logger import Logger


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
    #: Zero-based position in the list this came from. The tile badge shows
    #: `rank + 1`; it used to show the champion's index in the *filtered*
    #: backup row, which is not a number the user ever configured.
    rank: int = 0

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
        """Adopt a new application state snapshot and recompute if structure changed."""
        prev_state = self._state
        self._app_state = app_state
        self._state = app_state.champ_select

        structure_changed = (
            prev_state.active != self._state.active
            or prev_state.cell_id != self._state.cell_id
            or prev_state.local_role != self._state.local_role
            or prev_state.locked_in != self._state.locked_in
            or prev_state.selected_champion_id != self._state.selected_champion_id
            or prev_state.my_team != self._state.my_team
            or prev_state.their_team != self._state.their_team
            or prev_state.actions != self._state.actions
        )

        if structure_changed:
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

    @property
    def pending_action(self):
        """The draft action you can act on right now, or None.

        Derived from state that has already been pushed to us. It used to be
        answered by `DraftActions.can_act()`, a blocking LCU GET issued from
        `_render()` — once per second, during the one phase where latency
        matters most.
        """
        try:
            from services.draft_actions import current_action

            return current_action(self._session_dict())
        except Exception as exc:
            Logger.debug("ChampSelectViewmodel", "pending_action failed", exc=exc)
            return None

    @property
    def pending_action_type(self) -> str:
        """"pick", "ban" or "" — so the view can label its own button."""
        action = self.pending_action
        return getattr(action, "type", "") or ""

    @property
    def can_act(self) -> bool:
        return self.pending_action is not None

    # ------------------------------------------------------------ internals
    def _session_dict(self) -> Dict[str, Any]:
        """Rebuild the LCU-shaped session the draft services expect.

        `queueId` and the bans used to be omitted. `PriorityEngine._is_aram()`
        was therefore always False, so in ARAM this screen recommended from
        the Summoner's Rift list while the engine — reading the real session —
        picked from the ARAM one. The screen contradicted what would happen.
        """
        session: Dict[str, Any] = {
            "localPlayerCellId": self._state.cell_id,
            "myTeam": list(self._state.my_team or ()),
            "theirTeam": list(self._state.their_team or ()),
            "actions": [list(self._state.actions or ())],
            "bannedChampions": [
                {"championId": cid}
                for cid in (self._state.banned_champion_ids or ())
            ],
        }
        queue_id = self._state.queue_id
        if queue_id:
            session["queueId"] = queue_id
            session["gameConfig"] = {"queueId": queue_id}
        return session

    def _champ_name(self, champ_id: int) -> str:
        assets = getattr(self._container, "assets", None)
        getter = getattr(assets, "get_champ_name", None)
        if callable(getter):
            try:
                return getter(champ_id) or str(champ_id)
            except Exception as exc:
                Logger.debug("ChampSelectViewmodel", "_champ_name suppressed an error", exc=exc)
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
            # Attribute only a number that actually came from somewhere.
            source = scraper.winrate_source() if scraper else ""
            reasons.append(
                f"{wr:.1f}% WR ({source})" if source else f"{wr:.1f}% WR"
            )
        # `result.reason` reads "Priority rank #1 for role 'MIDDLE'" — the raw
        # role enum and an internal rank syntax, on the flagship card.
        reasons.append(
            "#{} in your {} list".format(
                result.rank + 1,
                ROLE_LABELS.get(role, role.title()) if role else "priority",
            )
        )
        if role:
            reasons.append("{} selected".format(ROLE_LABELS.get(role, role.title())))
        reasons.append("Available")
        if result.is_fallback:
            reasons.append("Earlier priorities unavailable")

        self._recommendation = Recommendation(
            champion_id=result.champion_id,
            name=name,
            key=self._champ_key(result.champion_id),
            confidence=self._confidence_for(
                result.rank, result.is_fallback, role_matched
            ),
            rank=result.rank,
            reasons=reasons,
            is_fallback=result.is_fallback,
            winrate=wr,
        )

        self._backups = self._compute_backups(
            session, result.champion_id, source_list=result.source_list
        )

    def _compute_backups(
        self, session: Dict[str, Any], chosen_id: int,
        source_list: Tuple[int, ...] = (), limit: int = 4,
    ) -> List[Recommendation]:
        """Next available priorities after the recommended one (§14)."""
        backups: List[Recommendation] = []

        # The list the engine actually consulted. Reading `priority_list`
        # directly meant that whenever a role or ARAM list was in play, the
        # Backups row listed champions from a different list than the
        # recommendation directly above it.
        raw = list(source_list or ())
        if not raw:
            config = getattr(self._container, "config", None)
            if config is None:
                return backups
            try:
                from core.config_keys import PRIORITY_LIST, read_champion_ids

                raw = read_champion_ids(config, PRIORITY_LIST)
            except Exception as exc:
                Logger.debug("ChampSelectViewmodel", "backup list unavailable", exc=exc)
                return backups

        try:
            from services.draft import ActionValidator  # type: ignore
        except Exception:
            ActionValidator = None  # type: ignore

        scraper = getattr(self._container, "scraper", None)

        for rank, champ_id in enumerate(raw):
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
                except Exception as exc:
                    Logger.debug("ChampSelectViewmodel", "_compute_backups suppressed an error", exc=exc)
            b_name = self._champ_name(cid)
            b_wr = scraper.get_winrate(b_name) if scraper else None
            b_reasons = ["#{} in the same list".format(rank + 1)]
            if b_wr is not None:
                b_reasons.append(f"{b_wr:.1f}% WR")
            backups.append(
                Recommendation(
                    champion_id=cid,
                    name=b_name,
                    key=self._champ_key(cid),
                    # Every backup used to be stamped MEDIUM regardless of
                    # where it actually sat in the list.
                    confidence=self._confidence_for(rank, True, True),
                    reasons=b_reasons,
                    winrate=b_wr,
                    rank=rank,
                )
            )
            if len(backups) >= limit:
                break
        return backups
