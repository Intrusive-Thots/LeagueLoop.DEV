import os
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestQtToastAndTray(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PySide6.QtWidgets import QWidget
        self.host = QWidget()
        self.host.resize(800, 600)

    def tearDown(self):
        self.host.deleteLater()

    def test_toast_creation_and_tones(self):
        from ui.qt.components.toast import LLToast, QtToastManager
        from ui.qt.components.status import Tone

        manager = QtToastManager(self.host)
        t_info = manager.show_info("Info message", "Info Title")
        self.assertEqual(t_info.tone, Tone.INFO)

        t_success = manager.show_success("Success message", "Success Title")
        self.assertEqual(t_success.tone, Tone.SUCCESS)

        t_err = manager.show_error("Error message", "Error Title")
        self.assertEqual(t_err.tone, Tone.DANGER)

        t_warn = manager.show_warning("Warning message", "Warning Title")
        self.assertEqual(t_warn.tone, Tone.WARNING)

        self.assertEqual(len(manager._active_toasts), 4)

        # Test dismiss
        t_info.dismiss()
        t_info._on_dismiss_finished()

    def test_system_tray_creation_and_actions(self):
        from ui.qt.widgets.system_tray import QtSystemTray

        mock_window = MagicMock()
        mock_window.container = MagicMock()

        tray = QtSystemTray(main_window=mock_window)
        self.assertIsNotNone(tray.contextMenu())

        # Test show window
        tray._show_window()
        mock_window.showNormal.assert_called_once()
        mock_window.activateWindow.assert_called_once()

        # Test toggle automation
        ctrl = mock_window.container.automation_controller
        ctrl.is_master_enabled = True
        tray._toggle_automation()
        ctrl.set_master.assert_called_with(False)
