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


class SourceLevelTests(unittest.TestCase):
    """Cheap greps for wiring mistakes that no headless test can observe."""

    def test_the_automation_controller_is_called_by_its_real_name(self):
        """`is_master_enabled` is not an attribute; it raised AttributeError.

        The automation hotkey and the tray menu item both used it, inside
        callbacks whose exceptions go nowhere, so both silently did nothing.
        """
        for rel in ("ui/qt/main_window.py", "ui/qt/widgets/system_tray.py"):
            self.assertNotIn("is_master_enabled", _text(rel), rel)

    def test_the_lcu_request_helper_is_never_called_with_a_json_keyword(self):
        """`ApiHandler.request(method, endpoint, data)` has no `json` param.

        Passing one raised TypeError, and the custom-status handler reported
        a failure for a status the client had in fact accepted.
        """
        for path in SRC.rglob("*.py"):
            body = path.read_text(encoding="utf-8-sig")
            for m in re.finditer(r"\.request\(\s*[\"'](?:GET|PUT|POST|PATCH|DELETE)[\"'][^\n]*", body):
                self.assertNotIn("json=", m.group(0), f"{path}: {m.group(0)}")

    def test_the_status_write_happens_in_exactly_one_place(self):
        """It used to be sent twice — once correctly, once fatally."""
        self.assertNotIn("/lol-chat/v1/me", _text("ui/qt/widgets/settings_tab.py"))

    def test_the_champion_context_menu_is_connected_once(self):
        """Two connections meant one right-click opened two identical menus."""
        body = _text("ui/qt/widgets/champion_grid.py")
        self.assertEqual(body.count("connect(self._show_champion_context_menu)"), 1)


class RoleFilterTests(unittest.TestCase):
    """The role chips called a method that did not exist."""

    def test_the_asset_manager_exposes_champion_roles(self):
        from services.asset_manager import AssetManager

        self.assertTrue(hasattr(AssetManager, "get_champ_roles"))

    def test_it_returns_a_tuple_and_never_raises(self):
        from services.asset_manager import AssetManager

        am = AssetManager.__new__(AssetManager)
        am.champ_roles = {103: ["MIDDLE"]}
        self.assertEqual(am.get_champ_roles(103), ("MIDDLE",))
        self.assertEqual(am.get_champ_roles(999), ())
        self.assertEqual(am.get_champ_roles("not a number"), ())

    def test_an_unknown_role_does_not_pass_a_specific_role_filter(self):
        """`if roles and ...` let every champion through when roles were empty,
        which is precisely the state the app was always in."""
        body = _text("ui/qt/widgets/champion_grid.py")
        self.assertNotIn("if roles and self.current_role.upper() not in", body)


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


class BanDialogTests(unittest.TestCase):
    """"Respect teammate hovers" was discarded unless a ban was also edited."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self):
        from core.config_keys import AUTO_BAN_RESPECT_HOVERS
        from ui.qt.widgets.ban_list_dialog import QtBanListDialog

        class Config:
            def __init__(self):
                self.d = {}

            def get(self, k, default=None):
                return self.d.get(k, default)

            def set(self, k, v):
                self.d[k] = v

        config = Config()
        return QtBanListDialog(config=config), config, AUTO_BAN_RESPECT_HOVERS

    def test_toggling_the_checkbox_writes_the_key_immediately(self):
        dlg, config, key = self._dialog()
        dlg.chk_respect.setChecked(False)
        self.assertIs(config.get(key), False)
        dlg.chk_respect.setChecked(True)
        self.assertIs(config.get(key), True)

    def test_a_numeric_id_is_not_shown_as_a_champion_name(self):
        dlg, _config, _key = self._dialog()

        class Assets:
            def get_champ_name(self, cid):
                return str(cid)  # the real fallback on a cache miss

        dlg.assets = Assets()
        self.assertEqual(dlg._champ_name(266), "266")  # falls through, not "a name"


class PriorityModeTests(unittest.TestCase):
    """The mode switch showed no current mode until it was clicked."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_a_mode_is_selected_on_first_open(self):
        from core.config_keys import PRIORITY_LIST
        from ui.qt.widgets.champion_list_tab import QtPriorityTab

        class Config:
            def __init__(self):
                self.d = {}

            def get(self, k, default=None):
                return self.d.get(k, default)

            def set(self, k, v):
                self.d[k] = v

        class Container:
            def __init__(self):
                self.config = Config()
                self.assets = None
                self.scraper = None

        tab = QtPriorityTab(container=Container())
        checked = [k for k, b in tab._mode_buttons.items() if b.isChecked()]
        self.assertEqual(checked, [PRIORITY_LIST])


if __name__ == "__main__":
    unittest.main()
