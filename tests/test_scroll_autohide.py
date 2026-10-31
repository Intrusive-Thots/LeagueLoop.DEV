import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ui.components.scroll_autohide import needs_scrollbar, autohide_scrollbar  # noqa: E402


class NeedsScrollbarTests(unittest.TestCase):
    def test_full_view_hides_bar(self):
        self.assertFalse(needs_scrollbar((0.0, 1.0)))

    def test_partial_view_shows_bar(self):
        self.assertTrue(needs_scrollbar((0.0, 0.4)))
        self.assertTrue(needs_scrollbar((0.6, 1.0)))

    def test_frame_without_scrollbar_is_left_alone(self):
        obj = object()
        self.assertIs(autohide_scrollbar(obj), obj)


class AutohideRenderTests(unittest.TestCase):
    def setUp(self):
        try:
            import customtkinter as ctk
            self.root = ctk.CTk()
        except Exception as exc:  # no display
            self.skipTest(f"Tk unavailable: {exc}")
        self.root.geometry("200x200")
        self.ctk = ctk

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _settle(self):
        for _ in range(10):
            self.root.update()

    def test_bar_hidden_when_empty_and_shown_on_overflow(self):
        sf = self.ctk.CTkScrollableFrame(self.root, height=120)
        sf.pack(fill="both", expand=True)
        autohide_scrollbar(sf)
        self._settle()
        self.assertEqual(sf._scrollbar.winfo_manager(), "")
        for i in range(30):
            self.ctk.CTkLabel(sf, text=f"row {i}").pack()
        self._settle()
        self.assertEqual(sf._scrollbar.winfo_manager(), "grid")
        # Lists swap their rows for an empty-state label; Tk keeps a master's
        # last size when *every* child goes, so leave one like the app does.
        for w in sf.winfo_children()[1:]:
            w.destroy()
        self._settle()
        self.assertEqual(sf._scrollbar.winfo_manager(), "")


if __name__ == "__main__":
    unittest.main()
