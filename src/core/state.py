"""
Application State Management Module
Centralized single source of truth for LeagueLoop UI and background service state.
"""
from typing import Any, Dict, List

from core.events import (
    EventBus,
    LCUConnectionEvent,
    GamePhaseChangedEvent,
    ChampionSelectedEvent,
)


class ApplicationState:
    """Centralized observable application state model."""

    def __init__(self):
        self._connected: bool = False
        self._phase: str = "None"
        self._summoner: Dict[str, Any] = {}
        self._selected_champion: Dict[str, Any] = {}
        self._lcu_port: int = 0
        self._active_account: str = ""

        # Legacy compatibility properties
        self.connected = False
        self.phase = "None"
        self.queue = None
        self.friends: List[Any] = []
        self.champs: List[Any] = []
        self.session = None
        self.lobby = None
        self.search_state = None
        self.settings: Dict[str, Any] = {}
        self.auto_accept: bool = True
        self.arena_synergy_enabled: bool = True
        self.assets = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def set_connected(self, status: bool, port: int = 0):
        """Mutates LCU connection status and dispatches LCUConnectionEvent."""
        if self._connected != status or self._lcu_port != port:
            self._connected = status
            self.connected = status
            self._lcu_port = port
            EventBus.publish(LCUConnectionEvent(connected=status, port=port))

    @property
    def game_phase(self) -> str:
        return self._phase

    def set_game_phase(self, phase: str):
        """Mutates gameflow phase and dispatches GamePhaseChangedEvent."""
        if self._phase != phase:
            self._phase = phase
            self.phase = phase
            EventBus.publish(GamePhaseChangedEvent(phase=phase))

    @property
    def current_summoner(self) -> Dict[str, Any]:
        return self._summoner

    def set_current_summoner(self, summoner: Dict[str, Any]):
        """Sets active summoner profile details."""
        self._summoner = summoner or {}

    @property
    def selected_champion(self) -> Dict[str, Any]:
        return self._selected_champion

    def set_selected_champion(
        self, champion_id: int, champion_name: str, is_intent: bool = False
    ):
        """Sets hovered/locked champion selection and dispatches ChampionSelectedEvent."""
        self._selected_champion = {
            "id": champion_id,
            "name": champion_name,
            "is_intent": is_intent,
        }
        EventBus.publish(
            ChampionSelectedEvent(
                champion_id=champion_id,
                champion_name=champion_name,
                is_intent=is_intent
            )
        )


# Global singleton instance for backward compatibility
State = ApplicationState()
