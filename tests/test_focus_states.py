import sys
import unittest
from unittest.mock import MagicMock, patch

class TestFocusStates(unittest.TestCase):

    def setUp(self):
        self.mock_widget = MagicMock()
        self.mock_widget.cget.side_effect = lambda key: 0 if key == "border_width" else "transparent"
        self.mock_widget.master = None
        self.mock_widget.winfo_exists.return_value = True
        self.mock_widget.winfo_children.return_value = []

    def test_apply_focus_ring(self):
        mods_to_mock = {
            'customtkinter': MagicMock(),
            'tkinter': MagicMock(),
        }
        with patch.dict(sys.modules, mods_to_mock):
            for mod in list(sys.modules.keys()):
                if mod.startswith('utils.focus_states'):
                    sys.modules.pop(mod, None)
            from utils.focus_states import apply_focus_ring

            widget = MagicMock()
            widget.cget.side_effect = lambda key: 0 if key == "border_width" else "transparent"
            widget.master = None
            widget.winfo_exists.return_value = True
            widget.winfo_children.return_value = []
            del widget._orig_border_width
            del widget._orig_border_color

            apply_focus_ring(widget, color="#C8AA6E", width=3)
            self.assertTrue(widget.bind.called)
            self.assertEqual(widget._orig_border_width, 0)
            self.assertEqual(widget._orig_border_color, "transparent")

    def test_scroll_to_widget(self):
        mods_to_mock = {
            'customtkinter': MagicMock(),
            'tkinter': MagicMock(),
        }
        with patch.dict(sys.modules, mods_to_mock):
            for mod in list(sys.modules.keys()):
                if mod.startswith('utils.focus_states'):
                    sys.modules.pop(mod, None)
            from utils.focus_states import scroll_to_widget

            scrollable_frame = MagicMock()
            canvas = MagicMock()
            scrollable_frame._parent_canvas = canvas
            canvas.winfo_exists.return_value = True
            canvas.winfo_rooty.return_value = 100
            canvas.winfo_height.return_value = 500
            canvas.yview.return_value = (0.0, 0.5)

            widget = MagicMock()
            widget.winfo_rooty.return_value = 650
            widget.winfo_height.return_value = 40

            scroll_to_widget(scrollable_frame, widget)
            self.assertTrue(canvas.yview_moveto.called)

if __name__ == '__main__':
    unittest.main()
