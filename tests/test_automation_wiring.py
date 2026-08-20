"""
The automation switches must actually drive the engine.

`create_automation()` was called only from the legacy CustomTkinter shell, so
in the Qt app `container.automation` was None: every toggle wrote a config key
that nothing read at runtime, and both `stop_requested` signals were connected
to nothing. The controls looked live and did nothing.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from core.events import EventBus
from core.state import StateManager
from services.automation_controller import AutomationController


class FakeEngine:
    def __init__(self, explode_on_start=False):
        self.running = False
        self.paused = False
        self.explode_on_start = explode_on_start
        self.calls = []

    def start(self, start_paused=False):
        self.calls.append("start")
        if self.explode_on_start:
            raise RuntimeError("no client")
        self.running = True

    def stop(self):
        self.calls.append("stop")
        self.running = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False


class FakeConfig:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


def build(explode=False, **cfg):
    engine = FakeEngine(explode_on_start=explode)
    state = StateManager(bus=EventBus)
    controller = AutomationController(engine, state, FakeConfig(**cfg))
    return controller, engine, state


class ControllerTests(unittest.TestCase):
    def test_starting_runs_the_engine_and_publishes_it(self):
        controller, engine, state = build()
        controller.start()
        self.assertTrue(engine.running)
        self.assertTrue(state.state.automation.running)

    def test_stopping_stops_the_engine_and_publishes_it(self):
        controller, engine, state = build()
        controller.start()
        controller.stop()
        self.assertFalse(engine.running)
        self.assertFalse(state.state.automation.running)

    def test_the_master_switch_persists_and_acts(self):
        controller, engine, _state = build()
        controller.set_master(True)
        self.assertTrue(engine.running)
        self.assertTrue(controller._config.get("automation_master"))

        controller.set_master(False)
        self.assertFalse(engine.running)
        self.assertFalse(controller._config.get("automation_master"))

    def test_startup_honours_the_saved_master_switch(self):
        """Otherwise you must flip the switch once per launch to run anything."""
        controller, engine, _state = build(automation_master=True)
        controller.apply_config()
        self.assertTrue(engine.running)

    def test_startup_stays_off_when_the_switch_is_off(self):
        controller, engine, _state = build(automation_master=False)
        controller.apply_config()
        self.assertFalse(engine.running)

    def test_starting_twice_is_a_no_op(self):
        controller, engine, _state = build()
        controller.start()
        controller.start()
        self.assertEqual(engine.calls.count("start"), 1)

    def test_a_failed_start_is_reported_not_swallowed(self):
        controller, engine, state = build(explode=True)
        controller.start()
        self.assertFalse(engine.running)
        self.assertFalse(state.state.automation.running)
        self.assertIn("no client", state.state.automation.last_error or "")

    def test_toggle_values_are_mirrored_into_state(self):
        controller, _engine, state = build(
            auto_accept=True, auto_lock_in=True, auto_requeue=False,
            auto_random_skin=False,
        )
        controller.publish()
        auto = state.state.automation
        self.assertTrue(auto.auto_accept)
        self.assertTrue(auto.auto_lock)
        self.assertFalse(auto.auto_requeue)
        self.assertFalse(auto.auto_skin)

    def test_pause_and_resume(self):
        controller, engine, state = build()
        controller.start()
        controller.pause(True)
        self.assertTrue(engine.paused)
        self.assertTrue(state.state.automation.paused)
        controller.pause(False)
        self.assertFalse(state.state.automation.paused)


class MirrorTests(unittest.TestCase):
    """The engine can stop itself; the UI must not keep claiming it is on."""

    def test_the_poller_republishes_when_the_engine_stops_itself(self):
        from services.client_state_service import ClientStateService

        controller, engine, state = build()
        controller.start()

        class DeadLcu:
            is_connected = False
            def connect(self, silent=False):
                return False
            def request(self, *a, **k):
                return None

        service = ClientStateService(
            DeadLcu(), state, automation_controller=controller,
            sleep=lambda _s: None,
        )
        engine.running = False  # engine died on its own
        service.tick()
        self.assertFalse(state.state.automation.running)


class WindowWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        from ui.qt.main_window import LeagueLoopMainWindow

        controller, engine, state = build()

        class Container:
            def __init__(self):
                self.state_manager = state
                self.automation_controller = controller
                self.config = controller._config

        return LeagueLoopMainWindow(container=Container()), controller, engine

    def test_the_emergency_stop_reaches_the_engine(self):
        window, controller, engine = self._window()
        controller.start()
        button = window.tab_pages["automation"].btn_stop
        button.setEnabled(True)
        button.click()
        self.assertIn("stop", engine.calls)
        self.assertFalse(engine.running)

    def test_the_draft_screens_stop_button_works_too(self):
        window, _controller, engine = self._window()
        page = window.tab_pages.get("champ_select")
        if not hasattr(page, "btn_stop"):
            self.skipTest("draft screen did not build")
        engine.running = True
        page.btn_stop.setEnabled(True)
        page.btn_stop.click()
        self.assertIn("stop", engine.calls)

    def test_the_master_switch_starts_the_engine(self):
        window, _controller, engine = self._window()
        window.tab_pages["automation"].master_toggle.set_checked(False)
        engine.calls.clear()
        window.tab_pages["automation"].master_toggle.set_checked(True)
        self.assertIn("start", engine.calls)


if __name__ == "__main__":
    unittest.main()
