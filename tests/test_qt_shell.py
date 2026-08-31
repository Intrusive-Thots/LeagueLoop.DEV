"""
Shell-level guards for the Qt migration.

The point of these is that the migration cannot quietly go backwards: every
navigation destination must resolve to a real screen, not the generic
"not migrated yet" placeholder.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class _Cfg:
    def __init__(self, data=None):
        self.d = dict(data or {})

    def get(self, key, default=None):
        return self.d.get(key, default)

    def set(self, key, value, save=True):
        self.d[key] = value

    def set_batch(self, updates, save=True):
        self.d.update(updates)


class _Container:
    """Minimal stand-in - no LCU, no Tk, no network."""

    def __init__(self):
        self.config = _Cfg()
        self.assets = None
        self.db = None
        self.lcu = None
        self.automation = None
        self.account_manager = None
        self.state_manager = None
        self.loot = None


class TestShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, container=None):
        from ui.qt.main_window import LeagueLoopMainWindow
        return LeagueLoopMainWindow(container=container)

    def test_every_nav_destination_has_a_real_screen(self):
        """No destination may fall back to the generic placeholder page."""
        from PySide6.QtWidgets import QWidget

        window = self._window(_Container())
        try:
            placeholders = [
                key
                for key, _name, _icon in window.sidebar.DEFAULT_TABS
                if type(window.tab_pages.get(key)) is QWidget
            ]
            self.assertEqual(
                placeholders, [], "these destinations are still placeholders"
            )
        finally:
            window.close()

    def test_shell_builds_without_a_container(self):
        """UI-only mode must work - it is how screenshots and CI run."""
        window = self._window(None)
        try:
            self.assertEqual(
                len(window.tab_pages), len(window.sidebar.DEFAULT_TABS)
            )
        finally:
            window.close()

    def test_champion_list_screens_use_distinct_config_keys(self):
        """Priority / ARAM / bans must not write over each other."""
        from ui.qt.widgets.champion_list_tab import (
            QtAramTab,
            QtBanListTab,
            QtPriorityTab,
        )

        keys = [
            QtPriorityTab.CONFIG_KEY,
            QtAramTab.CONFIG_KEY,
            QtBanListTab.CONFIG_KEY,
        ]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(
            set(keys), {"priority_list", "aram_priority_list", "ban_list"}
        )

    def test_champion_list_saves_to_its_own_key(self):
        from ui.qt.widgets.champion_list_tab import QtAramTab

        container = _Container()
        tab = QtAramTab(container=container)
        tab._on_champion_clicked(103, "Ahri")

        self.assertIn(103, container.config.get("aram_priority_list") or [])
        self.assertEqual(container.config.get("priority_list"), None)

    def test_profile_starts_empty_without_match_data(self):
        """§22: no fake placeholder data before a real match exists."""
        from ui.qt.widgets.profile_tab import QtProfileTab

        tab = QtProfileTab(container=_Container())
        self.assertEqual(tab.stack.currentIndex(), 0)

    def test_loot_open_button_disabled_until_something_is_openable(self):
        """Opening loot is irreversible - never enabled speculatively (§40)."""
        from ui.qt.widgets.loot_tab import QtLootTab

        tab = QtLootTab(container=_Container())
        self.assertFalse(tab.btn_open.isEnabled())


if __name__ == "__main__":
    unittest.main()


class PhaseDetailTests(unittest.TestCase):
    """
    The phase card is the biggest thing on the Play screen. "Lobby" on its
    own restates the label; it should name the queue and say what happens
    next (§56).
    """

    @classmethod
    def setUpClass(cls):
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _status(self, phase, queue_id=450, elapsed=0, connected=True):
        from core.state import ApplicationState, ClientState, QueueState
        from ui.qt.viewmodels.shell_viewmodel import ShellViewModel

        vm = ShellViewModel()
        vm.push_state(ApplicationState(
            client=ClientState(connected=connected, phase=phase),
            queue=QueueState(queue_id=queue_id, elapsed_s=elapsed),
        ))
        return vm.phase_status()

    def test_a_lobby_names_the_queue(self):
        _text, _tone, detail = self._status("Lobby")
        self.assertIn("ARAM", detail)
        self.assertIn("ready to search", detail)

    def test_queueing_shows_how_long(self):
        _text, _tone, detail = self._status("Matchmaking", 420, elapsed=95)
        self.assertIn("Ranked Solo", detail)
        self.assertIn("1:35", detail)

    def test_queueing_without_a_timer_still_reads(self):
        _text, _tone, detail = self._status("Matchmaking", 420, elapsed=0)
        self.assertIn("searching", detail)

    def test_a_disconnected_client_says_so_rather_than_idle(self):
        _text, _tone, detail = self._status("None", None, connected=False)
        self.assertIn("Waiting for the League Client", detail)

    def test_no_queue_id_does_not_leave_a_dangling_separator(self):
        _text, _tone, detail = self._status("Lobby", queue_id=None)
        self.assertFalse(detail.startswith("-"))
        self.assertFalse(detail.endswith("-"))


class FirstPaintTests(unittest.TestCase):
    """
    Views bind before the services publish. The view-model emits only on
    change, so anything rendering solely from those signals keeps its
    construction-time value — the footer said "Automation off" while the
    header said "Automation on". `refresh()` re-emits everything once.
    """

    @classmethod
    def setUpClass(cls):
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_refresh_re_emits_every_slice(self):
        from core.state import (
            ApplicationState, AutomationState, ClientState, QueueState,
        )
        from ui.qt.viewmodels.shell_viewmodel import ShellViewModel

        class Manager:
            def __init__(self, state): self.state = state

        state = ApplicationState(
            client=ClientState(connected=True, phase="Lobby"),
            queue=QueueState(queue_id=450),
            automation=AutomationState(running=True),
        )

        class Container:
            state_manager = Manager(state)

        vm = ShellViewModel(container=Container())
        seen = {"conn": [], "phase": [], "queue": [], "auto": [], "sum": []}
        vm.connection_changed.connect(lambda v: seen["conn"].append(v))
        vm.phase_changed.connect(lambda v: seen["phase"].append(v))
        vm.queue_changed.connect(lambda v: seen["queue"].append(v))
        vm.automation_changed.connect(lambda v: seen["auto"].append(v))
        vm.summary_changed.connect(lambda v: seen["sum"].append(v))

        vm.refresh()

        self.assertEqual(seen["conn"], [True])
        self.assertEqual(seen["phase"], ["Lobby"])
        self.assertEqual(seen["queue"], ["ARAM"])
        self.assertEqual(seen["auto"], [True])
        self.assertIn("Automation on", seen["sum"][0])

    def test_build_refreshes_so_header_and_footer_agree(self):
        import inspect
        from ui.qt.app import application

        self.assertIn("view_model.refresh()", inspect.getsource(application.build))

    def test_find_match_creates_lobby_and_starts_search(self):
        from unittest.mock import MagicMock
        from ui.qt.widgets.play_tab import QtPlayTab

        lcu = MagicMock()
        lcu.is_connected = True
        calls = []

        def mock_req(method, endpoint, data=None, silent=False):
            calls.append((method, endpoint, data))
            res = MagicMock()
            if endpoint == "/lol-lobby/v2/lobby/matchmaking/search-state":
                res.status_code = 404
            elif endpoint == "/lol-lobby/v2/lobby":
                res.status_code = 404 if method == "GET" else 200
            else:
                res.status_code = 200
            return res

        lcu.request.side_effect = mock_req

        container = MagicMock()
        container.lcu = lcu
        container.config = MagicMock()
        container.config.get.return_value = "ARAM"

        tab = QtPlayTab(container=container)
        tab._on_find_match()

        endpoints = [c[1] for c in calls]
        self.assertIn("/lol-lobby/v2/lobby", endpoints)
        self.assertIn("/lol-lobby/v2/lobby/matchmaking/search", endpoints)

