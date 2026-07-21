import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

# Ensure QApplication instance exists for PySide6 widget tests
app = QApplication.instance() or QApplication([])

from ui.qt.pages.settings_page import QtHotkeyRecorderButton


class TestHotkeyRecorder(unittest.TestCase):

    def setUp(self):
        self.recorded_val = None

        def _on_change(val):
            self.recorded_val = val

        self.btn = QtHotkeyRecorderButton(
            config_key="hotkey_find_match",
            initial_value="ctrl+shift+f",
            on_change=_on_change
        )

    def test_hotkey_recording_sequence(self):
        self.btn.start_recording()
        self.assertTrue(self.btn.recording)

        # Simulate pressing Shift alone (should be ignored)
        ev_shift = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Shift, Qt.ShiftModifier)
        self.btn.keyPressEvent(ev_shift)
        self.assertTrue(self.btn.recording)

        # Simulate Ctrl+Shift+A key combo
        ev_combo = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_A, Qt.ControlModifier | Qt.ShiftModifier)
        self.btn.keyPressEvent(ev_combo)

        self.assertFalse(self.btn.recording)
        self.assertEqual(self.btn.hotkey_value, "ctrl+shift+a")
        self.assertEqual(self.recorded_val, "ctrl+shift+a")

    def test_escape_cancels_recording(self):
        self.btn.start_recording()
        self.assertTrue(self.btn.recording)

        ev_esc = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        self.btn.keyPressEvent(ev_esc)

        self.assertFalse(self.btn.recording)
        self.assertEqual(self.btn.hotkey_value, "ctrl+shift+f")


if __name__ == "__main__":
    unittest.main()
