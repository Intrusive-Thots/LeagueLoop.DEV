from core.state import State
from core.events import EventBus

class StateManager:
    """
    Subscribes to EventBus and updates State in real-time.
    This eliminates the need for polling loops to keep state accurate.
    """
    def __init__(self):
        # Bind LCU Connection
        EventBus.on("lcu_connected", self._on_lcu_connected)
        
        # Bind Gameflow/Phase
        EventBus.on("OnJsonApiEvent_lol-gameflow_v1_gameflow-phase", self._on_phase)
        
        # Bind Champ Select
        EventBus.on("OnJsonApiEvent_lol-champ-select_v1_session", self._on_session)
        
        # Bind Lobby
        EventBus.on("OnJsonApiEvent_lol-lobby_v2_lobby", self._on_lobby)
        
        # Bind Matchmaking
        EventBus.on("OnJsonApiEvent_lol-matchmaking_v1_search", self._on_search)

        # Bind Friends List
        EventBus.on("OnJsonApiEvent_lol-chat_v1_friends", self._on_friends)

    def _on_lcu_connected(self, connected: bool):
        State.connected = connected
        if not connected:
            State.phase = "None"
        EventBus.emit("state_updated")

    def _on_phase(self, payload):
        phase = payload if isinstance(payload, str) else payload.get("data", "None")
        if State.phase != phase:
            State.phase = phase
            EventBus.emit("phase_changed", phase)
            EventBus.emit("state_updated")

    def _on_session(self, session):
        State.session = session
        EventBus.emit("champ_select_event", session)
        EventBus.emit("state_updated")

    def _on_lobby(self, lobby):
        State.lobby = lobby
        EventBus.emit("lobby_event", lobby)
        EventBus.emit("state_updated")

    def _on_search(self, search_state):
        State.search_state = search_state
        EventBus.emit("queue_event", search_state)
        EventBus.emit("state_updated")

    def _on_friends(self, friends_data):
        State.friends = friends_data
        EventBus.emit("friends_event", friends_data)
        EventBus.emit("state_updated")

# Initialize globally
_state_manager = StateManager()
