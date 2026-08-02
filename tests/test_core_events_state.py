import pytest
from unittest.mock import MagicMock
from core.events import _EventBus, EventBus
from core.state import AppState, State
from core.state_manager import StateManager

class TestEventBus:
    def test_event_bus_register_and_emit(self):
        bus = _EventBus()
        mock_cb = MagicMock()
        bus.on("test_event", mock_cb)
        bus.emit("test_event", 123, payload="data")
        mock_cb.assert_called_once_with(123, payload="data")

    def test_event_bus_off(self):
        bus = _EventBus()
        mock_cb = MagicMock()
        bus.on("test_event", mock_cb)
        bus.off("test_event", mock_cb)
        bus.emit("test_event")
        mock_cb.assert_not_called()

    def test_event_bus_duplicate_callback(self):
        bus = _EventBus()
        mock_cb = MagicMock()
        bus.on("test_event", mock_cb)
        bus.on("test_event", mock_cb)
        bus.emit("test_event")
        assert mock_cb.call_count == 1

    def test_event_bus_exception_handling(self):
        bus = _EventBus()
        def bad_cb():
            raise ValueError("Test error")
        bus.on("error_event", bad_cb)
        # Should catch and log error without raising
        bus.emit("error_event")

    def test_invoke_thread_safe_with_tk_widget(self):
        bus = _EventBus()
        widget = MagicMock()
        cb = MagicMock()
        bus.invoke_thread_safe(widget, cb, "arg1")
        widget.after.assert_called_once()

    def test_invoke_thread_safe_without_tk_widget(self):
        bus = _EventBus()
        widget = object()
        cb = MagicMock()
        bus.invoke_thread_safe(widget, cb, "arg1")
        cb.assert_called_once_with("arg1")


class TestAppState:
    def test_app_state_initialization(self):
        app_state = AppState()
        assert app_state.connected is False
        assert app_state.phase == "None"
        assert app_state.auto_accept is True
        assert app_state.arena_synergy_enabled is True
        assert isinstance(app_state.friends, list)

    def test_global_state_singleton(self):
        assert State is not None
        assert isinstance(State, AppState)


class TestStateManager:
    def test_state_manager_events(self):
        sm = StateManager()

        # Test LCU connected
        EventBus.emit("lcu_connected", True)
        assert State.connected is True

        EventBus.emit("lcu_connected", False)
        assert State.connected is False
        assert State.phase == "None"

        # Test Phase Change
        EventBus.emit("OnJsonApiEvent_lol-gameflow_v1_gameflow-phase", "ChampSelect")
        assert State.phase == "ChampSelect"

        EventBus.emit("OnJsonApiEvent_lol-gameflow_v1_gameflow-phase", {"data": "InProgress"})
        assert State.phase == "InProgress"

        # Test Champ Select session
        EventBus.emit("OnJsonApiEvent_lol-champ-select_v1_session", {"cellId": 1})
        assert State.session == {"cellId": 1}

        # Test Lobby
        EventBus.emit("OnJsonApiEvent_lol-lobby_v2_lobby", {"queueId": 420})
        assert State.lobby == {"queueId": 420}

        # Test Matchmaking
        EventBus.emit("OnJsonApiEvent_lol-matchmaking_v1_search", {"searchState": "Searching"})
        assert State.search_state == {"searchState": "Searching"}

        # Test Friends
        EventBus.emit("OnJsonApiEvent_lol-chat_v1_friends", [{"id": 1, "name": "Friend1"}])
        assert State.friends == [{"id": 1, "name": "Friend1"}]
