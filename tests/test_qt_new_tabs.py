"""
Unit tests for newly migrated Qt tabs, modals, overlays, and system integrations.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestQtNewTabsAndComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.temp_dir.name, "test_qt_new_tabs.db")
        from core.container import ApplicationContainer
        self.container = ApplicationContainer(db_path=db_path)

    def tearDown(self):
        self.container.shutdown()
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_aram_tab_initialization_and_prio_list(self):
        from ui.qt.widgets.aram_tab import QtAramTab

        tab = QtAramTab(container=self.container)
        self.assertIsNotNone(tab.grid)
        self.assertIsNotNone(tab.prio_list_widget)
        self.assertIsNotNone(tab.row_bench_swap)

        # Toggle bench sniper
        tab.row_bench_swap.set_checked(False)
        self.assertFalse(self.container.config.get("aram_bench_swap"))
        tab.row_bench_swap.set_checked(True)
        self.assertTrue(self.container.config.get("aram_bench_swap"))

        # Clear list first for test isolation
        tab._on_clear_all()
        self.assertEqual(len(self.container.config.get("aram_priority_list")), 0)

        # Add champion to ARAM prio list
        tab._on_champion_clicked(99, "Lux")
        self.assertIn(99, self.container.config.get("aram_priority_list"))
        self.assertEqual(tab.prio_list_widget.count(), 1)

        # Clear list again
        tab._on_clear_all()
        self.assertEqual(len(self.container.config.get("aram_priority_list")), 0)

    def test_loot_tab_initialization_and_actions(self):
        from ui.qt.widgets.loot_tab import QtLootTab

        tab = QtLootTab(container=self.container)
        self.assertIsNotNone(tab.btn_refresh)
        self.assertIsNotNone(tab.btn_open)
        self.assertIsNotNone(tab.status)

        # Test refresh callback without crashing
        tab.refresh()

    def test_accounts_tab_initialization_and_crud(self):
        from ui.qt.widgets.accounts_tab import QtAccountsTab

        tab = QtAccountsTab(container=self.container)
        self.assertIsNotNone(tab.active_card)
        self.assertIsNotNone(tab.active_status)
        self.assertIsNotNone(tab.list_card)

        # Test refresh callback without crashing
        tab.refresh()

    def test_ban_list_dialog(self):
        from ui.qt.widgets.ban_list_dialog import QtBanListDialog

        dlg = QtBanListDialog(config=self.container.config, assets=self.container.assets)
        self.assertIsNotNone(dlg.grid)
        self.assertIsNotNone(dlg.ban_list_widget)

        # Add champion ban
        dlg._on_champion_clicked(11, "Master Yi")
        self.assertIn(11, self.container.config.get("ban_list"))

        dlg._on_clear_all()
        self.assertEqual(len(self.container.config.get("ban_list")), 0)
        dlg.close()

    def test_hotkey_dialog(self):
        from ui.qt.widgets.hotkey_dialog import QtHotkeyDialog

        dlg = QtHotkeyDialog(action_name="Launch Client", current_key="Ctrl+Alt+L")
        self.assertEqual(dlg.recorded_sequence, "Ctrl+Alt+L")

        dlg._on_clear()
        self.assertEqual(dlg.recorded_sequence, "")
        dlg.close()

    def test_orb_widget(self):
        from ui.qt.widgets.orb_widget import QtOrbWidget

        orb = QtOrbWidget(container=self.container)
        self.assertIsNotNone(orb.btn_lock)
        self.assertIsNotNone(orb.btn_restore)

        # Emit restore request signal
        received = []
        orb.restore_requested.connect(lambda: received.append(True))
        orb.btn_restore.click()
        self.assertTrue(received)
        orb.close()

    def test_toast_manager(self):
        from ui.qt.components.toast import LLToastManager
        from ui.qt.components.status import Tone

        mgr = LLToastManager()
        toast = mgr.show_toast("Test Toast", "Operation completed successfully.", tone=Tone.SUCCESS, duration_ms=0)
        self.assertIsNotNone(toast)
        self.assertIn(toast, mgr.active_toasts)

        toast.dismiss()
        self.assertNotIn(toast, mgr.active_toasts)

    def test_system_tray_service(self):
        from ui.qt.widgets.system_tray import QtSystemTray

        tray = QtSystemTray(parent=None)
        self.assertIsNotNone(tray)

        # Test notification dispatch doesn't raise
        tray.showMessage("Test Title", "Test Message")


if __name__ == "__main__":
    unittest.main()
