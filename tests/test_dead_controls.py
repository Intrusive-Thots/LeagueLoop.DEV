"""
Controls that were on screen but reached nothing.

Every case here is a control a user could see, click, and get no effect from
— the failure mode that is worse than a missing feature, because the screen
claims the feature exists. They are pinned so they cannot come back.
"""
import os
import re
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"


def _text(rel):
    return (SRC / rel).read_text(encoding="utf-8-sig")


class RequeueTests(unittest.TestCase):
    """Auto Requeue: a switch on two screens, read by nothing."""

    def _engine(self, **cfg):
        from tests.test_automation_draft import engine

        eng = engine(**cfg)
        eng._cached_search_state = None
        eng._last_search_state_time = 0.0
        eng.last_phase = "Lobby"
        return eng

    def test_the_switch_is_read(self):
        eng = self._engine(auto_requeue=False)
        eng._handle_dodge_requeue("Lobby", prev_phase="ChampSelect")
        self.assertEqual(eng.lcu.calls, [])

    def test_a_dodge_requeues_when_the_switch_is_on(self):
        eng = self._engine(auto_requeue=True)
        eng._handle_dodge_requeue("Lobby", prev_phase="ChampSelect")
        self.assertIn(
            ("POST", "/lol-lobby/v2/lobby/matchmaking/search", None), eng.lcu.calls
        )

    def test_it_does_not_fire_without_a_preceding_draft(self):
        eng = self._engine(auto_requeue=True)
        eng._handle_dodge_requeue("Lobby", prev_phase="Lobby")
        self.assertEqual(eng.lcu.calls, [])


class AcceptTimerTests(unittest.TestCase):
    """A pending accept must not survive the emergency stop."""

    def _engine(self):
        from tests.test_automation_draft import engine

        eng = engine(auto_accept=True)
        eng.running = True
        eng.paused = False
        eng._accept_timer = None
        eng._stop_event = mock.Mock()
        eng._wake_event = mock.Mock()
        eng.lcu.stop_websocket = lambda: None
        return eng

    def test_stop_cancels_a_pending_accept(self):
        import threading

        eng = self._engine()
        fired = []
        eng._accept_timer = threading.Timer(30.0, lambda: fired.append(1))
        eng._accept_timer.daemon = True
        eng._accept_timer.start()
        eng.stop()
        self.assertIsNone(eng._accept_timer)
        self.assertEqual(fired, [])

    def test_pause_cancels_a_pending_accept(self):
        import threading

        eng = self._engine()
        eng._accept_timer = threading.Timer(30.0, lambda: None)
        eng._accept_timer.daemon = True
        eng._accept_timer.start()
        eng.pause()
        self.assertIsNone(eng._accept_timer)


class QueueDetectionTests(unittest.TestCase):
    """The queue id came from the lobby, which is gone once the draft starts."""

    def test_the_draft_reads_the_queue_id_from_the_session(self):
        body = _text("services/automation.py")
        self.assertIn('session.get("queueId")', body)


if __name__ == "__main__":
    unittest.main()
