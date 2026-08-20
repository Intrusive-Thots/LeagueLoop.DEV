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

    def test_dodge_recovers_navigation_and_emits_toast(self):
        """When someone dodges in draft, shell recovers cleanly to previous tab."""
        window = self._window(_Container())
        try:
            # Start on play tab
            window.sidebar.select_tab("play")
            self.assertEqual(window.sidebar.current_tab, "play")

            # Follow into draft
            window._on_phase_changed("ChampSelect")
            self.assertEqual(window.sidebar.current_tab, "champ_select")

            # Dodge occurs -> phase returns to Lobby
            toasts_shown = []
            window.toast_requested.connect(lambda msg, title, tone: toasts_shown.append((msg, title, tone)))
            window._on_phase_changed("Lobby")

            # Recovers to previous tab ("play") and shows toast
            self.assertEqual(window.sidebar.current_tab, "play")
            self.assertTrue(any("dodge" in msg.lower() for msg, _t, _tone in toasts_shown))
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
