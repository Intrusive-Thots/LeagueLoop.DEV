"""
Champ select actions — hovering, picking, banning.

The draft screen could not do any of these: `pick_requested` and
`override_requested` were emitted and connected to nothing.

The LCU models a draft as a list of *action groups*. Each action carries an
`id`, the `actorCellId` it belongs to, a `type` ("pick" / "ban"), and
`isInProgress` / `completed` flags. You act by PATCHing the action that is
both yours and in progress:

    PATCH /lol-champ-select/v1/session/actions/{id}   {"championId": 103}
    PATCH /lol-champ-select/v1/session/actions/{id}   {"championId": 103,
                                                       "completed": true}

Hovering and locking are the same call; `completed` is what commits it. A
PATCH to an action that is not in progress is rejected by the client, which
is why `current_action()` filters rather than taking the first one it finds.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from utils.logger import Logger

SESSION_ENDPOINT = "/lol-champ-select/v1/session"
ACTION_ENDPOINT = "/lol-champ-select/v1/session/actions/{}"


class ActionType(Enum):
    PICK = "pick"
    BAN = "ban"


class DraftError(Enum):
    """Why an action could not be performed. Each maps to a real sentence."""

    NONE = "none"
    NOT_CONNECTED = "not_connected"
    NO_SESSION = "no_session"
    NOT_YOUR_TURN = "not_your_turn"
    ALREADY_LOCKED = "already_locked"
    REJECTED = "rejected"


DRAFT_ERROR_MESSAGES = {
    DraftError.NONE: "",
    DraftError.NOT_CONNECTED: "The League Client is not connected.",
    DraftError.NO_SESSION: "You are not in champion select.",
    DraftError.NOT_YOUR_TURN: "It is not your turn yet.",
    DraftError.ALREADY_LOCKED: "You have already locked in.",
    DraftError.REJECTED: "The client rejected that champion.",
}


@dataclass(frozen=True)
class DraftAction:
    """One action from the live session."""

    id: int
    actor_cell_id: int
    type: str
    completed: bool = False
    in_progress: bool = False
    champion_id: int = 0

    @property
    def is_pick(self) -> bool:
        return self.type == ActionType.PICK.value

    @property
    def is_ban(self) -> bool:
        return self.type == ActionType.BAN.value


@dataclass(frozen=True)
class DraftResult:
    ok: bool
    error: DraftError = DraftError.NONE
    detail: str = ""

    @property
    def message(self) -> str:
        return self.detail or DRAFT_ERROR_MESSAGES.get(self.error, "")


def parse_actions(session: Dict[str, Any]) -> List[DraftAction]:
    """Flatten the LCU's nested action groups into typed actions."""
    actions: List[DraftAction] = []
    for group in session.get("actions") or ():
        for raw in group or ():
            if not isinstance(raw, dict):
                continue
            try:
                actions.append(
                    DraftAction(
                        id=int(raw.get("id", -1)),
                        actor_cell_id=int(raw.get("actorCellId", -1)),
                        type=str(raw.get("type") or ""),
                        completed=bool(raw.get("completed")),
                        in_progress=bool(raw.get("isInProgress")),
                        champion_id=int(raw.get("championId") or 0),
                    )
                )
            except (TypeError, ValueError):
                continue
    return actions


def current_action(
    session: Dict[str, Any], cell_id: Optional[int] = None
) -> Optional[DraftAction]:
    """
    The action you can act on right now, or None.

    Must be yours, in progress, and not already completed. Picking the first
    action with a matching cell id instead would PATCH a ban you already made,
    or a pick from a previous phase.
    """
    if cell_id is None:
        cell_id = session.get("localPlayerCellId")
    try:
        cell_id = int(cell_id)
    except (TypeError, ValueError):
        return None
    if cell_id < 0:
        return None

    for action in parse_actions(session):
        if (
            action.actor_cell_id == cell_id
            and action.in_progress
            and not action.completed
            and action.id >= 0
        ):
            return action
    return None


class DraftActions:
    """Perform champ select actions against the live client."""

    def __init__(self, lcu: Any):
        self._lcu = lcu

    # ------------------------------------------------------------- session
    def _session(self) -> Optional[Dict[str, Any]]:
        if not getattr(self._lcu, "is_connected", False):
            return None
        try:
            res = self._lcu.request("GET", SESSION_ENDPOINT, silent=True)
        except Exception:
            return None
        if res is None or getattr(res, "status_code", 0) != 200:
            return None
        try:
            payload = res.json()
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    # -------------------------------------------------------------- verbs
    def hover(self, champion_id: int) -> DraftResult:
        """Show the champion to your team without committing to it."""
        return self._apply(champion_id, completed=False)

    def lock_in(self, champion_id: int) -> DraftResult:
        """Commit the pick (or the ban, if a ban is what is in progress)."""
        return self._apply(champion_id, completed=True)

    def _apply(self, champion_id: int, completed: bool) -> DraftResult:
        if not getattr(self._lcu, "is_connected", False):
            return DraftResult(False, DraftError.NOT_CONNECTED)

        session = self._session()
        if session is None:
            return DraftResult(False, DraftError.NO_SESSION)

        action = current_action(session)
        if action is None:
            # Distinguish "you already locked" from "not your turn" - they
            # need different words and different UI states.
            cell_id = session.get("localPlayerCellId")
            mine = [
                a for a in parse_actions(session)
                if a.actor_cell_id == cell_id and a.is_pick
            ]
            if mine and all(a.completed for a in mine):
                return DraftResult(False, DraftError.ALREADY_LOCKED)
            return DraftResult(False, DraftError.NOT_YOUR_TURN)

        body: Dict[str, Any] = {"championId": int(champion_id)}
        if completed:
            body["completed"] = True

        try:
            res = self._lcu.request(
                "PATCH", ACTION_ENDPOINT.format(action.id), data=body, silent=True
            )
        except Exception as exc:
            Logger.debug("Draft", f"action PATCH raised: {exc}")
            return DraftResult(False, DraftError.REJECTED, str(exc))

        status = getattr(res, "status_code", 0) if res is not None else 0
        # The LCU answers 204 on success and 2xx generally; anything else is
        # a refusal (champion not owned, banned, already taken).
        if 200 <= status < 300:
            return DraftResult(True)

        detail = ""
        try:
            body_json = res.json() if res is not None else None
            if isinstance(body_json, dict):
                detail = str(body_json.get("message") or "")
        except Exception:
            pass
        return DraftResult(False, DraftError.REJECTED, detail)

    # ------------------------------------------------------------ queries
    def can_act(self) -> bool:
        session = self._session()
        return session is not None and current_action(session) is not None

    def pending_type(self) -> str:
        """"pick", "ban", or "" - so the UI can label its own button."""
        session = self._session()
        if session is None:
            return ""
        action = current_action(session)
        return action.type if action is not None else ""
