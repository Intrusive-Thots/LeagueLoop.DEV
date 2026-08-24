"""
The old shell's quick-toggle row must not lose controls it cannot fit.

Measured on the real window: the bar is 260px, the nine icons wanted 306px,
and `pack(side="left")` resolved that by squeezing the eighth icon to 20px and
giving the ninth — Auto-Ban — a width of **1 pixel at x=0**. It was not
clipped; it was not drawn at all, and there was no way to reach the toggle.
Tk shrinks and then drops rather than complaining, so nothing ever reported
it.

The rule is the one the champion grid uses: icons keep their size, the row
count gives way.

Needs Tk and a display; skips cleanly without either.
"""
import os
import unittest

try:
    import customtkinter  # noqa: F401
    import tkinter  # noqa: F401
    HAVE_TK = True
except Exception:                        # pragma: no cover - environment
    HAVE_TK = False

os.environ.setdefault("PYSTRAY_BACKEND", "dummy")

#: Panel widths to check: the shipped default, a comfortable one, and
#: narrower than the app should ever be.
WIDTHS = (240, 300, 380, 460)


@unittest.skipUnless(HAVE_TK, "CustomTkinter/Tk is not available here")
class QuickIconBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import customtkinter as ctk

        try:
            cls.root = ctk.CTk()
        except Exception as exc:         # pragma: no cover - no display
            raise unittest.SkipTest("no display available: %s" % exc)
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_the_column_count_never_drops_below_one(self):
        """A zero would place every icon in column zero, on top of itself."""
        from ui.app_sidebar import SidebarWidget

        widget = SidebarWidget.__new__(SidebarWidget)
        widget._quick_icon_widgets = {}
        for available in (0, 1, 5, 31, 32, 300):
            self.assertGreaterEqual(widget._quick_icon_columns(available), 1)

    def test_more_width_never_means_fewer_columns(self):
        from ui.app_sidebar import SidebarWidget

        widget = SidebarWidget.__new__(SidebarWidget)
        widget._quick_icon_widgets = {}
        counts = [widget._quick_icon_columns(w) for w in (100, 200, 400, 800)]
        self.assertEqual(counts, sorted(counts))

    def test_the_cell_size_is_measured_not_assumed(self):
        """CustomTkinter scales widgets, so a button asked for 26px is not
        26px everywhere. At nine icons a per-icon error of one pixel is a
        whole icon."""
        from ui.app_sidebar import SidebarWidget

        widget = SidebarWidget.__new__(SidebarWidget)

        class Button:
            def winfo_reqwidth(self):
                return 44

            def winfo_width(self):
                return 44

        widget._quick_icon_widgets = {"a": {"btn": Button()}}
        self.assertEqual(
            widget._quick_icon_cell(), 44 + 2 * SidebarWidget.QUICK_ICON_PAD,
        )

    def test_it_falls_back_to_the_nominal_size_before_first_layout(self):
        from ui.app_sidebar import SidebarWidget

        widget = SidebarWidget.__new__(SidebarWidget)
        widget._quick_icon_widgets = {}
        self.assertEqual(
            widget._quick_icon_cell(),
            SidebarWidget.QUICK_ICON_SIZE + 2 * SidebarWidget.QUICK_ICON_PAD,
        )


@unittest.skipUnless(HAVE_TK, "CustomTkinter/Tk is not available here")
class LiveWindowTests(unittest.TestCase):
    """The real application, at several widths. Slow, and worth it: every
    number in this file's docstring came from running it."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("LEAGUELOOP_LOG_DIR", "/tmp/leagueloop-tests")
        try:
            from core.main import LeagueLoopApp

            cls.app = LeagueLoopApp()
        except Exception as exc:         # pragma: no cover - no display
            raise unittest.SkipTest("could not build the shell: %s" % exc)
        cls._settle()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass

    @classmethod
    def _settle(cls, passes=40):
        for _ in range(passes):
            cls.app.update_idletasks()
            cls.app.update()

    def _icons(self):
        return [e["btn"] for e in self.app.sidebar._quick_icon_widgets.values()]

    def test_every_toggle_is_drawn_at_every_width(self):
        """Auto-Ban was 1px wide at x=0 — present in the tree, absent on
        screen, and impossible to click."""
        for width in WIDTHS:
            self.app.geometry("%dx520" % width)
            self._settle()
            for index, button in enumerate(self._icons()):
                self.assertGreater(
                    button.winfo_width(), 20,
                    "icon %d is %dpx wide at a %dpx panel"
                    % (index, button.winfo_width(), width),
                )

    def test_no_toggle_is_pushed_past_the_edge(self):
        bar = self.app.sidebar.quick_icon_bar
        for width in WIDTHS:
            self.app.geometry("%dx520" % width)
            self._settle()
            for index, button in enumerate(self._icons()):
                right = button.winfo_x() + button.winfo_width()
                self.assertLessEqual(
                    right, bar.winfo_width(),
                    "icon %d ends at %d in a %dpx bar"
                    % (index, right, bar.winfo_width()),
                )

    def test_the_icons_keep_their_size_and_the_rows_give_way(self):
        """Fewer per row, never smaller. Same rule as the champion grid."""
        sizes, rows = set(), set()
        for width in WIDTHS:
            self.app.geometry("%dx520" % width)
            self._settle()
            icons = self._icons()
            sizes.update(b.winfo_width() for b in icons)
            rows.add(len({b.winfo_y() for b in icons}))
        self.assertEqual(len(sizes), 1, "icons were resized: %s" % sorted(sizes))
        self.assertGreater(len(rows), 1, "the row count never adapted")

    def test_a_wide_panel_uses_a_single_row(self):
        self.app.geometry("460x520")
        self._settle()
        self.assertEqual(len({b.winfo_y() for b in self._icons()}), 1)


if __name__ == "__main__":
    unittest.main()
