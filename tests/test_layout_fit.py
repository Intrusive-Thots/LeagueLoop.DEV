"""
Content must fit the space it is given — at every panel width.

Two failure modes, and only one of them is what people mean by "overflow":

1. A child is drawn outside its parent. Visible, obvious, rare.
2. A layout cannot satisfy its children, so it shrinks them *below* their
   own minimum. Qt reports nothing. The button is still inside its card; it
   is just four characters wide with an ellipsis, and the champion grid grows
   a horizontal scrollbar it should never have needed.

The second is what the recording actually showed, and nothing in the suite
could see it. These tests measure both.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

#: Widths that matter: a narrow companion strip, the default panel, and a
#: comfortable desktop window.
WIDTHS = (240, 340, 480, 620, 900, 1280)


def _settle(app, passes: int = 14) -> None:
    """Nested scroll areas resize their viewports in a *later* layout pass,
    so one processEvents() measures a layout that has not finished."""
    for _ in range(passes):
        app.sendPostedEvents()
        app.processEvents()


class _Assets:
    """A roster large enough to need scrolling, with no network and no art."""

    def __init__(self, count: int = 170):
        self.champ_data = {
            "Champ%03d" % i: {"key": str(i + 1), "name": "Champion %03d" % i}
            for i in range(count)
        }

    def get_champ_roles(self, key):
        return []


class ChampionGridFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _grid(self):
        from ui.qt.widgets.champion_grid import QtChampionGrid

        grid = QtChampionGrid(asset_manager=_Assets())
        grid.load_champions()
        grid.resize(900, 700)
        grid.show()
        _settle(self.app)
        return grid

    def test_columns_adapt_and_nothing_is_pushed_off_the_edge(self):
        grid = self._grid()
        seen_counts = set()
        for width in WIDTHS:
            grid.resize(width, 700)
            _settle(self.app)
            viewport = grid.scroll_area.viewport()
            tiles = [t for t in grid.tiles.values() if t.isVisible()]
            self.assertTrue(tiles, "no tiles at %dpx" % width)
            escaping = [t for t in tiles if t.geometry().right() > viewport.width()]
            self.assertEqual(
                escaping, [],
                "%d tile(s) past the right edge at %dpx" % (len(escaping), width),
            )
            self.assertLessEqual(
                grid.grid_container.width(), viewport.width(),
                "the grid is wider than the space it has at %dpx" % width,
            )
            seen_counts.add(grid._columns)
        self.assertGreater(
            len(seen_counts), 1,
            "the column count never changed, so it is not responsive",
        )

    def test_tiles_keep_their_size_instead_of_being_shrunk_to_fit(self):
        """Density is a design decision. Fewer columns, not smaller icons."""
        grid = self._grid()
        widths = set()
        for width in WIDTHS:
            grid.resize(width, 700)
            _settle(self.app)
            widths.update(t.width() for t in grid.tiles.values() if t.isVisible())
        self.assertEqual(
            len(widths), 1,
            "tiles were resized to make columns fit: %s" % sorted(widths),
        )

    def test_a_narrow_panel_falls_back_to_one_column(self):
        grid = self._grid()
        grid.resize(180, 700)
        _settle(self.app)
        self.assertEqual(grid._columns, 1)
        self.assertFalse(
            grid.scroll_area.horizontalScrollBar().isVisible(),
            "the grid grew a horizontal scrollbar instead of using fewer columns",
        )

    def test_the_last_row_can_be_scrolled_into_full_view(self):
        """A champion you cannot reach is a champion you do not have."""
        grid = self._grid()
        for width in (340, 620, 1280):
            grid.resize(width, 500)
            _settle(self.app)
            bar = grid.scroll_area.verticalScrollBar()
            bar.setValue(bar.maximum())
            _settle(self.app, 6)
            tiles = [t for t in grid.tiles.values() if t.isVisible()]
            last = max(tiles, key=lambda t: (t.geometry().bottom(), t.geometry().right()))
            self.assertLessEqual(
                last.geometry().bottom() - bar.value(),
                grid.scroll_area.viewport().height(),
                "the final row is still cut off at %dpx after scrolling to the "
                "bottom" % width,
            )


class TabFitTests(unittest.TestCase):
    """Every tab, not just the one that happens to be on top."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        from ui.qt.main_window import LeagueLoopMainWindow

        cls.window = LeagueLoopMainWindow(container=None)
        cls.window.show()
        _settle(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()

    def _pages(self):
        for key, _name, _icon in self.window.sidebar.DEFAULT_TABS:
            button = self.window.sidebar.buttons.get(key)
            if button is not None:
                button.click()
            _settle(self.app)
            yield key, self.window.tab_stack.currentWidget()

    def test_no_tab_demands_more_width_than_the_window_can_give_it(self):
        """The check that would have caught the 1162px priority screen.

        The window's minimum is 760px and the sidebar takes 200 of it. A tab
        whose own minimum exceeds what is left is guaranteed to render
        squeezed — every label elided, every button a sliver — on a window
        the user is allowed to create.
        """
        from ui.qt.main_window import MIN_WIDTH

        available = MIN_WIDTH - self.window.sidebar.width()
        too_wide = {}
        for key, page in self._pages():
            wanted = page.minimumSizeHint().width()
            if wanted > available:
                too_wide[key] = wanted
        self.assertEqual(
            too_wide, {},
            "tab(s) wider than the %dpx a minimum-size window leaves them: %s"
            % (available, too_wide),
        )

    def test_nothing_is_rendered_smaller_than_its_own_minimum(self):
        import sys
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
        from check_overflow import find_squeezed
        from check_scaling import find_clipping

        for width in (760, 900, 1280):
            self.window.resize(width, 720)
            _settle(self.app)
            for key, page in self._pages():
                problems = find_clipping(page) + find_squeezed(page)
                self.assertEqual(
                    problems, [],
                    "%s at %dpx:\n  %s" % (key, width, "\n  ".join(problems)),
                )


if __name__ == "__main__":
    unittest.main()
