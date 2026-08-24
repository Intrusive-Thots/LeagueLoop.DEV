"""
ActivityViewModel — turns EventBus events into readable activity
(UI/UX Master Plan §18, §56).

This is the translation layer the plan asks for: events arrive as protocol
facts, and leave as product sentences.

    CHAMPION_SELECTED  ->  "Selected Jinx"
    LCU_DISCONNECTED   ->  "League Client disconnected"

Anything without a mapping is dropped rather than leaked as raw text, so the
feed cannot regress into a log tail.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from core.events import EventBus, EventType
from ui.qt.components.activity import ActivityEntry, ActivityKind
from utils.logger import Logger

#: event -> (template, kind, category, important)
#: `{}` in a template is filled from the event payload where available.
EVENT_MAP: Dict[str, Tuple[str, ActivityKind, str, bool]] = {
    EventType.LCU_CONNECTED.value:
        ("Connected to the League Client", ActivityKind.SUCCESS, "LCU", True),
    EventType.LCU_DISCONNECTED.value:
        ("League Client disconnected", ActivityKind.WARNING, "LCU", True),
    EventType.QUEUE_FOUND.value:
        ("Match found", ActivityKind.INFO, "AUTOMATION", True),
    EventType.QUEUE_ACCEPTED.value:
        ("Ready check accepted", ActivityKind.SUCCESS, "AUTOMATION", True),
    EventType.QUEUE_DECLINED.value:
        ("Ready check declined", ActivityKind.WARNING, "AUTOMATION", True),
    EventType.CHAMP_SELECT_STARTED.value:
        ("Champion select started", ActivityKind.INFO, "AUTOMATION", False),
    EventType.CHAMP_SELECT_ENDED.value:
        ("Champion select ended", ActivityKind.NEUTRAL, "AUTOMATION", False),
    EventType.CHAMPION_SELECTED.value:
        ("Selected {}", ActivityKind.SUCCESS, "AUTOMATION", True),
    EventType.CHAMPION_BANNED.value:
        ("Banned {}", ActivityKind.SUCCESS, "AUTOMATION", True),
    EventType.AUTOMATION_STARTED.value:
        ("Automation started", ActivityKind.SUCCESS, "AUTOMATION", True),
    EventType.AUTOMATION_STOPPED.value:
        ("Automation stopped", ActivityKind.WARNING, "AUTOMATION", True),
    EventType.AUTOMATION_PAUSED.value:
        ("Automation paused", ActivityKind.WARNING, "AUTOMATION", True),
    EventType.AUTOMATION_ERROR.value:
        ("Automation error: {}", ActivityKind.ERROR, "AUTOMATION", True),
    EventType.ACCOUNT_CHANGED.value:
        ("Switched account to {}", ActivityKind.INFO, "AUTOMATION", True),
    EventType.LOBBY_CREATED.value:
        ("Lobby created", ActivityKind.INFO, "AUTOMATION", False),
    EventType.LOBBY_JOINED.value:
        ("Joined a lobby", ActivityKind.INFO, "AUTOMATION", False),
    EventType.LOBBY_LEFT.value:
        ("Left the lobby", ActivityKind.NEUTRAL, "AUTOMATION", False),
}


def _payload_text(payload: Any) -> str:
    """Best-effort readable detail from an arbitrary event payload."""
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("name", "champion", "champion_name", "account", "message", "error"):
            value = payload.get(key)
            if value:
                return str(value)
        return ""
    data = getattr(payload, "data", None)
    if isinstance(data, dict):
        return _payload_text(data)
    return ""


def translate(event_name: str, payload: Any = None) -> Optional[ActivityEntry]:
    """Map an event to an activity entry, or None if it has no user meaning."""
    mapping = EVENT_MAP.get(event_name)
    if mapping is None:
        return None

    template, kind, category, important = mapping
    detail = _payload_text(payload)
    if "{}" in template:
        if not detail:
            return None          # nothing meaningful to say - stay quiet
        text = template.format(detail)
    else:
        text = template

    return ActivityEntry(text=text, kind=kind, category=category,
                         important=important)


class ActivityViewModel(QObject):
    """Subscribes to the EventBus and emits ready-to-render entries."""

    entry_added = Signal(object)   # ActivityEntry

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._handles = []
        self._handlers = []
        self._subscribe()

    def _subscribe(self) -> None:
        for event_name in EVENT_MAP:
            handler = self._make_handler(event_name)
            self._handlers.append(handler)   # keep a strong reference
            try:
                self._handles.append(EventBus.on(event_name, handler))
            except Exception as exc:
                Logger.debug("ActivityViewmodel", "_subscribe suppressed an error", exc=exc)

    def _make_handler(self, event_name: str) -> Callable:
        def _handler(payload: Any = None, *_args, **_kwargs) -> None:
            entry = translate(event_name, payload)
            if entry is not None:
                self.entry_added.emit(entry)
        return _handler

    def dispose(self) -> None:
        for handle in self._handles:
            try:
                handle.dispose()
            except Exception as exc:
                Logger.debug("ActivityViewmodel", "dispose suppressed an error", exc=exc)
        self._handles.clear()
        self._handlers.clear()
