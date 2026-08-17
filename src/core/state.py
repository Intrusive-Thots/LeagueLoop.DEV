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

    def _notify_state_change(self) -> None:
        if self._bus:
            self._bus.emit(EventType.STATE_CHANGED, {"state": self._state})
