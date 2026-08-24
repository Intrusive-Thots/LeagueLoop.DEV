"""
Central State Model for LeagueLoop.
Provides immutable, typed state representations and thread-safe StateManager.
"""
from __future__ import annotations

import dataclasses
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple

from core.events import EventBus, EventType


@dataclass(frozen=True)
class ClientWindowState:
    """Where the League Client's window is on screen.

    Published by ``ClientWindowTracker``, consumed by ``CompanionAnchor``
    to keep the companion panel glued to the client.

    Frozen so it is hashable and can live inside ``ApplicationState``.
    """

    found: bool = False
    hwnd: int = 0
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    visible: bool = False
    minimized: bool = False
    #: HMONITOR of the display the window is on. 0 = unknown.
    monitor: int = 0
    #: Effective DPI of that display. 96 = 100 %. 0 = unknown.
    dpi: int = 0

    @property
    def usable(self) -> bool:
        """True when the client is visible, not minimised, and has a rect."""
        return (
            self.found
            and self.visible
            and not self.minimized
            and self.width > 0
            and self.height > 0
        )

    @property
    def scale(self) -> float:
        """Display scale factor derived from DPI (96 DPI = 1.0×)."""
        return (self.dpi or 96) / 96.0

    @property
    def rect(self) -> Tuple[int, int, int, int]:
        """(x, y, width, height) — the format ``place_companion`` expects."""
        return (self.x, self.y, self.width, self.height)

    @property
    def geometry_key(self) -> Tuple:
        """A hashable snapshot used to suppress duplicate publishes."""
        return (
            self.found, self.hwnd,
            self.x, self.y, self.width, self.height,
            self.visible, self.minimized,
            self.monitor, self.dpi,
        )


class AppState:
    """Legacy mutable application state for backward compatibility."""
    def __init__(self):
        self.connected = False
        self.phase = "None"
        self.auto_accept = True
        self.arena_synergy_enabled = True
        self.friends = []
        self.session = None
        self.lobby = None
        self.search_state = None


State = AppState()


class ConnectionStateEnum(Enum):
    """LCU connection finite state machine states."""
    DISCONNECTED = "DISCONNECTED"
    DISCOVERING = "DISCOVERING"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"


class GameflowPhase(Enum):
    """League client gameflow phases."""
    NONE = "None"
    LOBBY = "Lobby"
    MATCHMAKING = "Matchmaking"
    READY_CHECK = "ReadyCheck"
    CHAMP_SELECT = "ChampSelect"
    IN_PROGRESS = "InProgress"
    PRE_END_OF_GAME = "PreEndOfGame"
    END_OF_GAME = "EndOfGame"
    WAITING_FOR_STATS = "WaitingForStats"
    SPECTATING = "Spectating"


@dataclass(frozen=True)
class ClientState:
    """LCU Connection and Authenticated Summoner State."""
    connected: bool = False
    connection_state: ConnectionStateEnum = ConnectionStateEnum.DISCONNECTED
    phase: str = "None"
    summoner_name: Optional[str] = None
    summoner_id: Optional[int] = None
    puuid: Optional[str] = None
    profile_icon_id: int = 0


@dataclass(frozen=True)
class QueueState:
    """Current Lobby / Matchmaking Queue State."""
    queue_id: Optional[int] = None
    queue_name: str = ""
    is_searching: bool = False
    estimated_delay_s: float = 0.0
    elapsed_s: float = 0.0


@dataclass(frozen=True)
class ChampSelectState:
    """Live Champion Selection State."""
    active: bool = False
    cell_id: int = -1
    local_role: str = ""
    timer_remaining_s: float = 0.0
    locked_in: bool = False
    selected_champion_id: int = 0
    my_team: Tuple[Dict[str, Any], ...] = ()
    their_team: Tuple[Dict[str, Any], ...] = ()
    actions: Tuple[Dict[str, Any], ...] = ()
    #: The draft's own queue id. Without it `PriorityEngine._is_aram()` is
    #: always False, so the screen recommends from the Summoner's Rift list
    #: while the engine — reading the real session — picks from the ARAM one.
    queue_id: Optional[int] = None
    #: Every champion the client considers banned. Completed ban *actions*
    #: are not the whole picture — the session carries its own `bans` block —
    #: and a frozen dataclass must stay hashable, so this is a flat tuple of
    #: ids rather than the raw structure.
    banned_champion_ids: Tuple[int, ...] = ()
    #: Champions this account can pick right now. Empty means "not known",
    #: which callers must not read as "all of them".
    pickable_champion_ids: Tuple[int, ...] = ()


@dataclass(frozen=True)
class AutomationState:
    """Automation Engine Operation and Toggle State."""
    running: bool = False
    paused: bool = False
    active_action: Optional[str] = None
    auto_accept: bool = False
    auto_lock: bool = False
    auto_requeue: bool = False
    auto_skin: bool = True
    last_error: Optional[str] = None


@dataclass(frozen=True)
class AccountState:
    """Active Account and Profile State."""
    active_account: Optional[str] = None
    all_accounts: Tuple[str, ...] = ()
    is_switching: bool = False


@dataclass(frozen=True)
class UIState:
    """Presentation Layer Navigation & Overlay State."""
    current_tab: str = "play"
    compact_mode: bool = False
    status_message: str = "Idle"


@dataclass(frozen=True)
class ApplicationState:
    """Complete Central Immutable Application State."""
    client: ClientState = field(default_factory=ClientState)
    queue: QueueState = field(default_factory=QueueState)
    champ_select: ChampSelectState = field(default_factory=ChampSelectState)
    automation: AutomationState = field(default_factory=AutomationState)
    account: AccountState = field(default_factory=AccountState)
    ui: UIState = field(default_factory=UIState)
    client_window: ClientWindowState = field(default_factory=ClientWindowState)


class StateManager:
    """
    Thread-safe Central State Container.
    Allows atomic state transitions and emits EventType.STATE_CHANGED on modifications.
    """

    def __init__(self, bus: Optional[EventBus] = None):
        self._bus = bus
        self._lock = threading.RLock()
        self._state = ApplicationState()

    @property
    def state(self) -> ApplicationState:
        """Read the current immutable application state snapshot."""
        with self._lock:
            return self._state

    def update_client(self, **kwargs) -> ApplicationState:
        """Atomically update ClientState fields."""
        with self._lock:
            new_client = dataclasses.replace(self._state.client, **kwargs)
            self._state = dataclasses.replace(self._state, client=new_client)
            self._notify_state_change()
            return self._state

    def update_queue(self, **kwargs) -> ApplicationState:
        """Atomically update QueueState fields."""
        with self._lock:
            new_queue = dataclasses.replace(self._state.queue, **kwargs)
            self._state = dataclasses.replace(self._state, queue=new_queue)
            self._notify_state_change()
            return self._state

    def update_champ_select(self, **kwargs) -> ApplicationState:
        """Atomically update ChampSelectState fields."""
        with self._lock:
            new_cs = dataclasses.replace(self._state.champ_select, **kwargs)
            self._state = dataclasses.replace(self._state, champ_select=new_cs)
            self._notify_state_change()
            return self._state

    def update_automation(self, **kwargs) -> ApplicationState:
        """Atomically update AutomationState fields."""
        with self._lock:
            new_auto = dataclasses.replace(self._state.automation, **kwargs)
            self._state = dataclasses.replace(self._state, automation=new_auto)
            self._notify_state_change()
            return self._state

    def update_account(self, **kwargs) -> ApplicationState:
        """Atomically update AccountState fields."""
        with self._lock:
            new_acc = dataclasses.replace(self._state.account, **kwargs)
            self._state = dataclasses.replace(self._state, account=new_acc)
            self._notify_state_change()
            return self._state

    def update_ui(self, **kwargs) -> ApplicationState:
        """Atomically update UIState fields."""
        with self._lock:
            new_ui = dataclasses.replace(self._state.ui, **kwargs)
            self._state = dataclasses.replace(self._state, ui=new_ui)
            self._notify_state_change()
            return self._state

    def update_client_window(self, **kwargs) -> ApplicationState:
        """Atomically update ClientWindowState fields."""
        with self._lock:
            new_cw = dataclasses.replace(self._state.client_window, **kwargs)
            self._state = dataclasses.replace(self._state, client_window=new_cw)
            self._notify_state_change()
            return self._state

    def _notify_state_change(self) -> None:
        """
        Publish the new state.

        Emits the *string* channel name. The EventBus keys listeners by the
        exact object passed to `emit`, and this used to pass the `EventType`
        enum member while every subscriber in the codebase uses the string -
        so a subscriber written the obvious way silently never fired.
        `ShellViewModel` was carrying a workaround that subscribed to both.
        """
        if self._bus:
            self._bus.emit(EventType.STATE_CHANGED.value, {"state": self._state})
