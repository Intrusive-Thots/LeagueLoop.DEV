import unittest
from core.state import ApplicationState
from core.events import EventBus, LCUConnectionEvent, GamePhaseChangedEvent, ChampionSelectedEvent


class TestApplicationState(unittest.TestCase):

    def setUp(self):
        self.state = ApplicationState()

    def test_set_connected_publishes_event(self):
        captured = []
        handle = EventBus.on(LCUConnectionEvent, lambda ev: captured.append(ev))

        self.state.set_connected(True, port=25280)

        self.assertTrue(self.state.is_connected)
        self.assertTrue(self.state.connected)
        self.assertEqual(len(captured), 1)
        self.assertTrue(captured[0].connected)
        self.assertEqual(captured[0].port, 25280)

        handle.unsubscribe()

    def test_set_game_phase_publishes_event(self):
        captured = []
        handle = EventBus.on(GamePhaseChangedEvent, lambda ev: captured.append(ev))

        self.state.set_game_phase("ChampSelect")

        self.assertEqual(self.state.game_phase, "ChampSelect")
        self.assertEqual(self.state.phase, "ChampSelect")
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].phase, "ChampSelect")

        handle.unsubscribe()

    def test_set_selected_champion_publishes_event(self):
        captured = []
        handle = EventBus.on(ChampionSelectedEvent, lambda ev: captured.append(ev))

        self.state.set_selected_champion(111, "Nautilus", is_intent=True)

        self.assertEqual(self.state.selected_champion["name"], "Nautilus")
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].champion_name, "Nautilus")
        self.assertTrue(captured[0].is_intent)

        handle.unsubscribe()


if __name__ == "__main__":
    unittest.main()
