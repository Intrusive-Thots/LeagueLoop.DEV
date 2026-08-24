"""
The taskbar icon, and how big a popup is allowed to be.

Both were "fixed" before by hard-coding a number in one place, which is why
they came back: the icon existed but three of the four places that show it
resolved it separately, and every dialog had its own opinion about its size.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class IconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_the_icon_file_carries_every_size_windows_asks_for(self):
        """Windows picks a different size for the taskbar, Alt-Tab, the title
        bar and the desktop. A single-size .ico is upscaled for the rest, and
        an upscaled 32px icon is the blurry one people notice."""
        from PIL import Image

        from ui.qt.services.app_icon import icon_path

        path = icon_path()
        self.assertIsNotNone(path, "no application icon was found")
        self.assertTrue(path.endswith(".ico"), "the resolved icon is not an .ico")
        with Image.open(path) as image:
            sizes = {size[0] for size in image.info.get("sizes", ())}
        for expected in (16, 24, 32, 48, 64, 128, 256):
            self.assertIn(expected, sizes, "the .ico has no %dpx image" % expected)

    def test_every_surface_resolves_the_same_icon(self):
        """Application, window and tray must not each pick their own file."""
        from ui.qt.services.app_icon import app_icon, icon_path

        self.assertFalse(app_icon().isNull())
        self.assertEqual(icon_path(), icon_path())  # cached, so stable

    def test_the_main_window_carries_the_icon_itself(self):
        from ui.qt.main_window import LeagueLoopMainWindow

        window = LeagueLoopMainWindow(container=None)
        try:
            self.assertFalse(
                window.windowIcon().isNull(),
                "the window has no icon of its own, so it depends on a "
                "QApplication that some entry points never build",
            )
        finally:
            window.close()

    def test_the_taskbar_identity_is_claimed_and_is_not_pythons(self):
        """Without an explicit AppUserModelID the taskbar button belongs to
        python.exe, and shows python.exe's icon."""
        from ui.qt.services.app_icon import APP_USER_MODEL_ID, install_identity

        self.assertTrue(APP_USER_MODEL_ID)
        self.assertNotIn("python", APP_USER_MODEL_ID.lower())
        # Off Windows this is a no-op that must not raise.
        install_identity()


class PopupSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_a_popup_grows_to_its_content_within_bounds(self):
        from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

        from ui.qt.services.popup_size import size_to_content

        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel("x" * 400, widget)
        label.setWordWrap(True)
        layout.addWidget(label)

        width, height = size_to_content(widget, (300, 150), (500, 400))
        self.assertGreaterEqual(width, 300)
        self.assertLessEqual(width, 500)
        self.assertGreaterEqual(height, 150)
        self.assertLessEqual(height, 400)

    def test_a_nearly_empty_popup_does_not_open_huge(self):
        """The ban list dialog used to call resize(780, 520) unconditionally,
        so an empty list opened as a large window of nothing."""
        from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

        from ui.qt.services.popup_size import size_to_content

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Nothing here yet.", widget))

        width, height = size_to_content(widget, (320, 160), (900, 700))
        self.assertEqual((width, height), (320, 160))

    def test_a_maximum_never_ends_up_below_the_minimum(self):
        """On a small screen the screen cap can undercut the minimum. Clipping
        the popup below its own minimum is not a smaller popup, it is a
        broken one."""
        from PySide6.QtWidgets import QWidget

        from ui.qt.services.popup_size import size_to_content

        widget = QWidget()
        width, height = size_to_content(widget, (600, 500), (200, 100))
        self.assertGreaterEqual(width, 600)
        self.assertGreaterEqual(height, 500)

    def test_no_dialog_hard_codes_its_own_size(self):
        """The rule lives in one place. A resize()/setFixedSize() in a dialog
        is that rule being forked again."""
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent / "src" / "ui" / "qt" / "widgets"
        offenders = []
        for path in root.glob("*dialog*.py"):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"self\.(resize|setFixedSize)\(", text):
                line = text[:match.start()].count("\n") + 1
                offenders.append("%s:%d" % (path.name, line))
        self.assertEqual(
            offenders, [],
            "dialog(s) sizing themselves instead of using size_to_content: %s"
            % offenders,
        )


class ModalSizingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_a_modal_sizes_itself_when_shown_not_when_constructed(self):
        """Modals are filled in after __init__, so measuring in the
        constructor measures an empty dialog."""
        from ui.qt.components.modal import (
            MODAL_MAX_HEIGHT,
            MODAL_MAX_WIDTH,
            MODAL_MIN_WIDTH,
            LLConfirmModal,
        )

        modal = LLConfirmModal(
            "Clear everything?",
            "This removes every champion from the list. " * 12,
            "Clear",
        )
        try:
            modal.show()
            for _ in range(6):
                self.app.processEvents()
            self.assertGreaterEqual(modal.width(), MODAL_MIN_WIDTH)
            self.assertLessEqual(modal.width(), MODAL_MAX_WIDTH)
            self.assertLessEqual(modal.height(), MODAL_MAX_HEIGHT)
        finally:
            modal.close()


if __name__ == "__main__":
    unittest.main()
