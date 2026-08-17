import unittest
from unittest.mock import MagicMock

from core.events import EventBus, EventType
from core.state import (
    ApplicationState,
    ClientState,
    ConnectionStateEnum,
    GameflowPhase,
    QueueState,
    ChampSelectState,
    AutomationState,
    StateManager,
)


class TestStateAndEvents(unittest.TestCase):
    def test_state_manager_transitions_and_bus_notification(self):
        bus = EventBus
        received_events = []
        handle = bus.on(EventType.STATE_CHANGED, lambda e: received_events.append(e))

        manager = StateManager(bus=bus)
        self.assertEqual(manager.state.client.connection_state, ConnectionStateEnum.DISCONNECTED)

        # Update client state
        manager.update_client(
            connected=True,
            connection_state=ConnectionStateEnum.CONNECTED,
            summoner_name="Faker",
            puuid="faker-puuid-1",
        )

        self.assertTrue(manager.state.client.connected)
        self.assertEqual(manager.state.client.connection_state, ConnectionStateEnum.CONNECTED)
        self.assertEqual(manager.state.client.summoner_name, "Faker")
        self.assertGreater(len(received_events), 0)

        # Update automation state
        manager.update_automation(running=True, auto_accept=True)
        self.assertTrue(manager.state.automation.running)
        self.assertTrue(manager.state.automation.auto_accept)

        # Update champ select state
        manager.update_champ_select(active=True, selected_champion_id=103, local_role="MIDDLE")
        self.assertTrue(manager.state.champ_select.active)
        self.assertEqual(manager.state.champ_select.selected_champion_id, 103)
        self.assertEqual(manager.state.champ_select.local_role, "MIDDLE")

        handle.dispose()

    def test_immutable_state_cannot_be_mutated_directly(self):
        state = ClientState(connected=True, summoner_name="Rookie")
        with self.assertRaises(Exception):
            state.connected = False  # Frozen dataclass should reject direct attribute modification


if __name__ == "__main__":
    unittest.main()
