"""
ShellViewModel — binds ApplicationState to the Qt shell
(UI/UX Master Plan §2.1 "State First", §2.4 "Persistent Context", §5).

This is the seam the migration audit called for: views render from
`core.state.ApplicationState` instead of polling services or calling the LCU
directly. The view-model subscribes to the EventBus, derives *presentation*
values (label + semantic tone + detail), and re-emits them as Qt signals.

Threading: the EventBus dispatches from background threads. Qt signals
emitted from a non-GUI thread are automatically queued to the receiver's
thread, so widgets connected to these signals are updated safely on the GUI
thread without any manual marshalling.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from core.events import EventBus, EventType
from core.state import ApplicationState, GameflowPhase
from ui.qt.components.status import Tone

# --- Presentation maps (§56: product vocabulary, never log-speak) ----------

#: Gameflow phase -> human label shown in the header/footer.
PHASE_LABELS = {
    GameflowPhase.NONE.value: "Idle",
    GameflowPhase.LOBBY.value: "Lobby",
    GameflowPhase.MATCHMAKING.value: "In queue",
    GameflowPhase.READY_CHECK.value: "Match found",
    GameflowPhase.CHAMP_SELECT.value: "Champ Select",
    GameflowPhase.IN_PROGRESS.value: "In game",
    GameflowPhase.PRE_END_OF_GAME.value: "Post game",
    GameflowPhase.END_OF_GAME.value: "Post game",
    GameflowPhase.WAITING_FOR_STATS.value: "Post game",
    GameflowPhase.SPECTATING.value: "Spectating",
}

#: Riot queue id -> display name. Mirrors core.constants queue ids.
QUEUE_NAMES = {
    400: "Draft Pick",
    420: "Ranked Solo",
    440: "Ranked Flex",
    450: "ARAM",
    1700: "Arena",
    1710: "Arena 3v6",
}


def phase_label(phase: str) -> str:
    """Human-readable label for a gameflow phase."""
    return PHASE_LABELS.get(phase, phase or "Idle")


def queue_label(queue_id: Optional[int], fallback: str = "") -> str:
    """Human-readable label for a queue id."""
    if queue_id is None:
        return fallback
    return QUEUE_NAMES.get(queue_id, fallback or f"Queue {queue_id}")


class ShellViewModel(QObject):
    """
    Presentation state for the persistent header, footer and mode switching.

    Views should connect to the granular signals and call the `*_status()`
    helpers to get a ready-to-render (text, tone, detail) triple.
    """

    #: Full snapshot changed — for views that re-render wholesale.
    state_changed = Signal(object)

    #: Granular signals, emitted only when that slice actually changes.
    connection_changed = Signal(bool)
    phase_changed = Signal(str)
    queue_changed = Signal(str)
    automation_changed = Signal(bool)
    summary_changed = Signal(str)

    def __init__(self, container: Any = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._container = container
        self._state_manager = getattr(container, "state_manager", None) if container else None
        self._state: ApplicationState = (
            self._state_manager.state if self._state_manager else ApplicationState()
        )

        # Cached slice values for change detection.
        self._last_connected: Optional[bool] = None
        self._last_phase: Optional[str] = None
        self._last_queue: Optional[str] = None
        self._last_automation: Optional[bool] = None
        self._last_summary: Optional[str] = None

        self._handles = []
        self._subscribe()

    # ------------------------------------------------------------ wiring
    def _subscribe(self) -> None:
        """
        Listen for state changes.

        This used to subscribe to both the `EventType.STATE_CHANGED` enum
        member and its `.value` string, because the bus keyed listeners by
        the exact object passed in and `StateManager` emitted the enum while
        everything else emitted the string. `EventBus` now normalises both to
        the same channel, so one subscription is enough.
        """
        self._on_state_event_ref = self._on_state_event  # keep a strong ref
        try:
            self._handles.append(
                EventBus.on(EventType.STATE_CHANGED, self._on_state_event_ref)
            )
        except Exception:
            pass

    def dispose(self) -> None:
        """Unsubscribe from the event bus."""
        for handle in self._handles:
            try:
                handle.dispose()
            except Exception:
                pass
        self._handles.clear()

    def _on_state_event(self, payload: Any = None, *args, **kwargs) -> None:
        """
        EventBus callback. Accepts the {'state': ApplicationState} payload.

        The bus dispatches from a background thread, and the window can be
        torn down between the emit and the delivery - Qt then raises
        "Signal source has been deleted" from inside the bus, which the bus
        logs as an error on every subsequent tick. Unsubscribing on the way
        out is cheaper than logging it forever.
        """
        try:
            import shiboken6

            if not shiboken6.isValid(self):
                self.dispose()
                return
        except Exception:
            pass

        state = None
        if isinstance(payload, dict):
            state = payload.get("state")
        elif isinstance(payload, ApplicationState):
            state = payload
        elif hasattr(payload, "data") and isinstance(getattr(payload, "data"), dict):
            state = payload.data.get("state")

        if state is None and self._state_manager is not None:
            state = self._state_manager.state
        if state is None:
            return

        self.push_state(state)

    # ------------------------------------------------------------- state
    @property
    def state(self) -> ApplicationState:
        return self._state

    def push_state(self, state: ApplicationState) -> None:
        """Adopt a new state snapshot and emit only what changed."""
        self._state = state
        try:
            self.state_changed.emit(state)
        except RuntimeError:
            # The underlying QObject went away mid-dispatch.
            self.dispose()
            return

        connected = bool(state.client.connected)
        if connected != self._last_connected:
            self._last_connected = connected
            self.connection_changed.emit(connected)

        phase = state.client.phase or GameflowPhase.NONE.value
        if phase != self._last_phase:
            self._last_phase = phase
            self.phase_changed.emit(phase)

        queue = queue_label(state.queue.queue_id, state.queue.queue_name)
        if queue != self._last_queue:
            self._last_queue = queue
            self.queue_changed.emit(queue)

        automation_on = bool(state.automation.running and not state.automation.paused)
        if automation_on != self._last_automation:
            self._last_automation = automation_on
            self.automation_changed.emit(automation_on)

        summary = self.footer_summary()
        if summary != self._last_summary:
            self._last_summary = summary
            self.summary_changed.emit(summary)

    def refresh(self) -> None:
        """Force a re-emit from the authoritative state (used on first paint)."""
        state = self._state_manager.state if self._state_manager else self._state
        # Reset caches so every granular signal fires once.
        self._last_connected = None
        self._last_phase = None
        self._last_queue = None
        self._last_automation = None
        self._last_summary = None
        self.push_state(state)

    # ------------------------------------------------- presentation helpers
    def connection_status(self) -> Tuple[str, Tone, str]:
        """(text, tone, detail) for the connection indicator (§20, §51)."""
        client = self._state.client
        conn_state = getattr(client.connection_state, "value", str(client.connection_state))

        if client.connected:
            return ("Connected", Tone.SUCCESS, client.summoner_name or "League Client ready")
        if conn_state in ("RECONNECTING", "CONNECTING", "DISCOVERING"):
            return ("Reconnecting", Tone.WARNING, "Looking for the League Client")
        return ("Disconnected", Tone.DANGER, "League Client not running")

    def phase_status(self) -> Tuple[str, Tone, str]:
        """(text, tone, detail) for the current gameflow phase."""
        phase = self._state.client.phase or GameflowPhase.NONE.value
        label = phase_label(phase)

        # Name the queue wherever one applies. "Lobby" on its own tells you
        # something you can already see; "Lobby - ARAM - ready to search" is
        # the sentence you actually wanted (§56, product vocabulary).
        queue = queue_label(self._state.queue.queue_id, self._state.queue.queue_name)

        def with_queue(text: str) -> str:
            return "{} - {}".format(queue, text) if queue else text

        if phase == GameflowPhase.CHAMP_SELECT.value:
            return (label, Tone.ACCENT, with_queue("draft in progress"))
        if phase == GameflowPhase.READY_CHECK.value:
            return (label, Tone.WARNING, with_queue("accept or decline"))
        if phase == GameflowPhase.MATCHMAKING.value:
            elapsed = self._state.queue.elapsed_s or 0
            waited = (
                "in queue {:d}:{:02d}".format(int(elapsed) // 60, int(elapsed) % 60)
                if elapsed else "searching for a match"
            )
            return (label, Tone.INFO, with_queue(waited))
        if phase == GameflowPhase.IN_PROGRESS.value:
            return (label, Tone.INFO, with_queue("match running"))
        if phase == GameflowPhase.LOBBY.value:
            return (label, Tone.NEUTRAL, with_queue("ready to search"))
        if phase == GameflowPhase.NONE.value:
            connected = self._state.client.connected
            return (
                label, Tone.NEUTRAL,
                "Nothing in progress" if connected
                else "Waiting for the League Client",
            )
        return (label, Tone.NEUTRAL, with_queue(""))

    def automation_status(self) -> Tuple[str, Tone, str]:
        """(text, tone, detail) for the automation indicator (§2.5)."""
        auto = self._state.automation
        if not auto.running:
            return ("Automation off", Tone.NEUTRAL, "Nothing will run automatically")
        if auto.paused:
            return ("Automation paused", Tone.WARNING, auto.active_action or "Paused")
        return ("Automation on", Tone.SUCCESS, auto.active_action or "Ready")

    def queue_status(self) -> Tuple[str, Tone, str]:
        """(text, tone, detail) for the selected queue."""
        queue = self._state.queue
        label = queue_label(queue.queue_id, queue.queue_name)
        if not label:
            return ("No queue", Tone.NEUTRAL, "")
        if queue.is_searching:
            return (label, Tone.INFO, "Searching")
        return (label, Tone.NEUTRAL, "")

    def footer_summary(self) -> str:
        """
        The one-line footer summary (§3, §57).

        Targets the plan's density: enough to orient, not a telemetry dump.
        e.g. "Champ Select • Ranked Solo • Automation on"
        """
        parts = []

        phase = self._state.client.phase or GameflowPhase.NONE.value
        if self._state.client.connected:
            parts.append(phase_label(phase))
        else:
            parts.append("League Client disconnected")

        queue = queue_label(self._state.queue.queue_id, self._state.queue.queue_name)
        if queue:
            parts.append(queue)

        auto = self._state.automation
        if auto.running:
            parts.append("Automation paused" if auto.paused else "Automation on")
        else:
            parts.append("Automation off")

        return "  •  ".join(p for p in parts if p)
