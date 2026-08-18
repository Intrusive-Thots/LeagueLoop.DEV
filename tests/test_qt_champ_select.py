"""
Tests for the Qt draft surfaces (UI/UX Master Plan §11-§16).

Deliberately free of any CustomTkinter dependency so they run in headless CI:
they touch only PySide6, `core.state` and `services.draft`.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class _QtTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])


class TestSemanticTimer(_QtTestCase):
    def test_classify_thresholds(self):
        from ui.qt.components.timer import TimerState, classify

        self.assertIs(classify(60.0), TimerState.SAFE)
        self.assertIs(classify(15.1), TimerState.SAFE)
        self.assertIs(classify(15.0), TimerState.ATTENTION)
        self.assertIs(classify(8.1), TimerState.ATTENTION)
        self.assertIs(classify(8.0), TimerState.URGENT)
        self.assertIs(classify(0.1), TimerState.URGENT)
        self.assertIs(classify(0.0), TimerState.EXPIRED)
        self.assertIs(classify(-5.0), TimerState.EXPIRED)

    def test_format_clock(self):
        from ui.qt.components.timer import format_clock

        self.assertEqual(format_clock(0), "00:00")
        self.assertEqual(format_clock(8), "00:08")
        self.assertEqual(format_clock(75), "01:15")
        self.assertEqual(format_clock(-3), "00:00")

    def test_states_are_distinguishable_without_colour(self):
        """§13/§62: colour must never be the only signal."""
        from ui.qt.components.timer import _STATE_SPEC

        glyphs = [glyph for _colour, glyph in _STATE_SPEC.values()]
        self.assertEqual(len(glyphs), len(set(glyphs)), "timer glyphs must be unique")

    def test_widget_updates_caption_and_digits(self):
        from ui.qt.components.timer import LLTimer, TimerState

        timer = LLTimer("Select now", 18.0)
        self.assertIs(timer.state, TimerState.SAFE)
        self.assertEqual(timer.digits.text(), "00:18")

        timer.set_remaining(5.0)
        self.assertIs(timer.state, TimerState.URGENT)
        self.assertEqual(timer.digits.text(), "00:05")

        timer.set_remaining(0.0)
        self.assertIs(timer.state, TimerState.EXPIRED)
        self.assertIn("TIME UP", timer.caption.text())


class TestDraftTimeline(_QtTestCase):
    def test_current_and_phase_selection(self):
        from ui.qt.components.draft_timeline import LLDraftTimeline

        timeline = LLDraftTimeline()
        self.assertEqual(timeline.current_index, 0)

        timeline.set_current_phase("PICK")
        self.assertEqual(timeline.phases()[timeline.current_index], "PICK")

        # Unknown phases are ignored rather than throwing.
        timeline.set_current_phase("NOT_A_PHASE")
        self.assertEqual(timeline.phases()[timeline.current_index], "PICK")

    def test_index_is_clamped(self):
        from ui.qt.components.draft_timeline import LLDraftTimeline

        timeline = LLDraftTimeline()
        timeline.set_current(99)
        self.assertEqual(timeline.current_index, len(timeline.phases()) - 1)
        timeline.set_current(-4)
        self.assertEqual(timeline.current_index, 0)

    def test_step_glyphs_unique(self):
        from ui.qt.components.draft_timeline import _STEP_SPEC

        glyphs = [glyph for _colour, glyph in _STEP_SPEC.values()]
        self.assertEqual(len(glyphs), len(set(glyphs)))


class _Cfg:
    def __init__(self, data=None):
        self.d = dict(data or {})

    def get(self, key, default=None):
        return self.d.get(key, default)

    def set(self, key, value, save=True):
        self.d[key] = value


class _Assets:
    NAMES = {222: "Jinx", 22: "Ashe", 103: "Ahri"}
    id_to_key = {222: "Jinx", 22: "Ashe", 103: "Ahri"}

    def get_champ_name(self, cid):
        return self.NAMES.get(cid, str(cid))

    def get_champ_roles(self, cid):
        return ["BOTTOM"] if cid in (222, 22) else ["MIDDLE"]


class _Container:
    def __init__(self, priority=None):
        # NB: `priority or [...]` would swallow an intentional empty list.
        if priority is None:
            priority = [222, 22, 103]
        self.config = _Cfg({"priority_list": list(priority)})
        self.assets = _Assets()


class TestChampSelectViewModel(_QtTestCase):
    def _state(self, **kwargs):
        from core.state import (
            ApplicationState,
            AutomationState,
            ChampSelectState,
            ClientState,
            GameflowPhase,
        )

        cs_kwargs = dict(
            active=True, cell_id=0, local_role="BOTTOM", timer_remaining_s=20.0,
            my_team=({"cellId": 0, "championId": 0, "assignedPosition": "bottom"},),
            actions=({"actorCellId": 0, "type": "pick", "isInProgress": True,
                      "completed": False},),
        )
        cs_kwargs.update(kwargs.pop("champ_select", {}))
        return ApplicationState(
            client=ClientState(connected=True, phase=GameflowPhase.CHAMP_SELECT.value),
            automation=kwargs.pop("automation", AutomationState(running=True)),
            champ_select=ChampSelectState(**cs_kwargs),
        )

    def test_role_label_mapping(self):
        from ui.qt.viewmodels.champ_select_viewmodel import ChampSelectViewModel

        vm = ChampSelectViewModel(container=_Container())
        vm.apply(self._state())
        self.assertEqual(vm.role_label, "ADC")

        vm.apply(self._state(champ_select={"local_role": "UTILITY"}))
        self.assertEqual(vm.role_label, "Support")

        vm.apply(self._state(champ_select={"local_role": ""}))
        self.assertEqual(vm.role_label, "Unassigned")

    def test_recommendation_from_priority_engine(self):
        from ui.qt.viewmodels.champ_select_viewmodel import (
            ChampSelectViewModel,
            Confidence,
        )

        vm = ChampSelectViewModel(container=_Container())
        vm.apply(self._state())

        rec = vm.recommendation
        self.assertTrue(rec.valid)
        self.assertEqual(rec.name, "Jinx")
        self.assertIs(rec.confidence, Confidence.HIGH)
        self.assertTrue(rec.reasons)

    def test_confidence_is_categorical_not_a_percentage(self):
        """§14 forbids fake precision like '97.42% confidence'."""
        from ui.qt.viewmodels.champ_select_viewmodel import Confidence

        values = {c.value for c in Confidence}
        self.assertEqual(values, {"High", "Medium", "Low", "Blocked"})
        for value in values:
            self.assertNotIn("%", value)

    def test_backups_exclude_the_recommendation(self):
        from ui.qt.viewmodels.champ_select_viewmodel import ChampSelectViewModel

        vm = ChampSelectViewModel(container=_Container())
        vm.apply(self._state())
        names = [b.name for b in vm.backups]
        self.assertNotIn(vm.recommendation.name, names)
        self.assertIn("Ashe", names)

    def test_blocked_when_no_priorities_configured(self):
        from ui.qt.viewmodels.champ_select_viewmodel import (
            ChampSelectViewModel,
            Confidence,
        )

        vm = ChampSelectViewModel(container=_Container(priority=[]))
        vm.apply(self._state())
        self.assertFalse(vm.recommendation.valid)
        self.assertIs(vm.recommendation.confidence, Confidence.BLOCKED)

    def test_timer_label_tracks_phase(self):
        from ui.qt.viewmodels.champ_select_viewmodel import ChampSelectViewModel

        vm = ChampSelectViewModel(container=_Container())
        vm.apply(self._state())
        self.assertEqual(vm.timer_label(), "Select now")

        vm.apply(self._state(champ_select={"locked_in": True}))
        self.assertEqual(vm.timer_label(), "Locked in")

    def test_automation_summary_reflects_engine_state(self):
        from core.state import AutomationState
        from ui.qt.viewmodels.champ_select_viewmodel import ChampSelectViewModel

        vm = ChampSelectViewModel(container=_Container())

        vm.apply(self._state(automation=AutomationState(running=False)))
        self.assertIn("off", vm.automation_summary().lower())

        vm.apply(self._state(automation=AutomationState(running=True, paused=True)))
        self.assertIn("paused", vm.automation_summary().lower())

        vm.apply(self._state(automation=AutomationState(running=True)))
        self.assertIn("Jinx", vm.automation_summary())


class TestQtSourceGuards(unittest.TestCase):
    """Guards for crash classes already hit once."""

    def test_no_raw_int_setweight(self):
        """
        Qt 6 requires QFont.Weight; passing a raw int raises TypeError, and a
        TypeError inside paintEvent with a live QPainter segfaults PySide6.
        """
        import re
        from pathlib import Path

        qt_root = Path(__file__).resolve().parents[1] / "src" / "ui" / "qt"
        offenders = []
        for path in qt_root.rglob("*.py"):
            for num, line in enumerate(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            ):
                if re.search(r"\.setWeight\(", line) and "QFont.Weight" not in line:
                    offenders.append(f"{path.name}:{num}")
        self.assertEqual(offenders, [], "use QFont.Weight(...) not a raw int")

    def test_asset_manager_imports_without_customtkinter(self):
        """
        The service layer must not require the old UI toolkit.

        `services.asset_manager` used to `import customtkinter` at module
        scope, which pulls in tkinter. That made every test touching
        ApplicationContainer - including the *Qt* tab tests - unrunnable in a
        headless environment. The import is now optional.
        """
        import re
        from pathlib import Path

        src = Path(__file__).resolve().parents[1] / "src" / "services" / "asset_manager.py"
        text = src.read_text(encoding="utf-8")

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("import customtkinter") or stripped.startswith(
                "from customtkinter"
            ):
                self.assertTrue(
                    line.startswith("    "),
                    "customtkinter must be imported inside a try/except, not at module scope",
                )

        # And it must actually import.
        import importlib

        importlib.import_module("services.asset_manager")

    def test_global_stylesheet_does_not_paint_every_widget(self):
        """
        A background-color on the universal QWidget selector makes every child
        paint over its parent card, which shows up as stray dark rectangles.
        """
        from ui.qt.theme import get_global_stylesheet

        import re

        qss = get_global_stylesheet()
        universal_block = qss.split("QMainWindow")[0].split("QWidget {")[-1].split("}")[0]
        # Match a declaration start, so `selection-background-color` (which is
        # fine) does not trip the guard.
        offending = re.search(r"(^|;|\s)background-color\s*:", universal_block)
        self.assertIsNone(
            offending,
            "QWidget must not set background-color; containers opt in instead",
        )


if __name__ == "__main__":
    unittest.main()
