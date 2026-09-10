"""
Consolidated unit tests for UI utility modules:
- Color utilities
- Focus states
- Smooth scroll
- Acrylic blur (Windows-specific)
- ARAM list window
- UI kwargs/factory
"""
import sys
import unittest
from unittest.mock import patch, MagicMock

# Mock dependencies before importing
mods_to_mock = {
    'customtkinter': MagicMock(),
    'tkinter': MagicMock(),
    'tkinterdnd2': MagicMock(),
    'tkinterdnd2.TkinterDnD': MagicMock(),
    'PIL': MagicMock(),
    'PIL.Image': MagicMock(),
}
_patcher = None
hex_to_rgb = None
interpolate_color = None
lighten_color = None
darken_color = None
parse_hex_rgb = None
ctk_safe_color = None
apply_focus_ring = None
scroll_to_widget = None
apply_smooth_scroll = None

def setUpModule():
    global _patcher
    global hex_to_rgb, interpolate_color, lighten_color, darken_color
    global parse_hex_rgb, ctk_safe_color
    global apply_focus_ring, scroll_to_widget, apply_smooth_scroll
    _patcher = patch.dict(sys.modules, mods_to_mock)
    _patcher.start()

    from ui.components.color_utils import (
        hex_to_rgb as h2r,
        interpolate_color as ic,
        lighten_color as lc,
        darken_color as dc,
        parse_hex_rgb as phr,
        ctk_safe_color as csc,
    )
    from utils.focus_states import apply_focus_ring as afr, scroll_to_widget as stw
    from utils.smooth_scroll import apply_smooth_scroll as ass
    
    hex_to_rgb = h2r
    interpolate_color = ic
    lighten_color = lc
    darken_color = dc
    parse_hex_rgb = phr
    ctk_safe_color = csc
    apply_focus_ring = afr
    scroll_to_widget = stw
    apply_smooth_scroll = ass

def tearDownModule():
    global _patcher
    if _patcher:
        _patcher.stop()
    for mod in list(sys.modules.keys()):
        if mod.startswith('ui.') or mod.startswith('utils.'):
            sys.modules.pop(mod, None)

class TestColorUtils(unittest.TestCase):
    def test_hex_to_rgb_6_char(self):
        self.assertEqual(hex_to_rgb("#FFFFFF"), (255, 255, 255))
        self.assertEqual(hex_to_rgb("#000000"), (0, 0, 0))
        self.assertEqual(hex_to_rgb("#FF0000"), (255, 0, 0))
        self.assertEqual(hex_to_rgb("#1A2B3C"), (26, 43, 60))

    def test_hex_to_rgb_3_char(self):
        self.assertEqual(hex_to_rgb("#FFF"), (255, 255, 255))
        self.assertEqual(hex_to_rgb("#000"), (0, 0, 0))
        self.assertEqual(hex_to_rgb("#F00"), (255, 0, 0))
        self.assertEqual(hex_to_rgb("#123"), (17, 34, 51))

    def test_hex_to_rgb_invalid(self):
        with self.assertRaises(ValueError):
            hex_to_rgb("#FF")
        with self.assertRaises(ValueError):
            hex_to_rgb("#ZZZZZZ")

    def test_interpolate_color(self):
        self.assertEqual(interpolate_color("#000000", "#ffffff", 0.5), "#7f7f7f")
        self.assertEqual(interpolate_color("#102030", "#ffffff", 0.0), "#102030")
        self.assertEqual(interpolate_color("transparent", "#ffffff", 0.5), "transparent")

    def test_lighten_darken_color(self):
        self.assertEqual(lighten_color("#000000", 50), "#7f7f7f")
        self.assertEqual(darken_color("#ffffff", 50), "#7f7f7f")
        self.assertEqual(lighten_color("transparent", 10), "transparent")

    def test_parse_hex_rgb_accepts_common_forms(self):
        self.assertEqual(parse_hex_rgb("#FFF"), (255, 255, 255))
        self.assertEqual(parse_hex_rgb("#1A2B3C"), (26, 43, 60))
        self.assertEqual(parse_hex_rgb("C8A45D33"), (200, 164, 93))
        self.assertEqual(parse_hex_rgb(("#091428", "#141E28")), (9, 20, 40))

    def test_parse_hex_rgb_rejects_named_junk_without_raising(self):
        """'invalid'[1:3] == 'nv' used to flood error.log via int(..., 16)."""
        for junk in ("invalid", "#canvas", "canvas", "transparent", None, "", "navy"):
            self.assertIsNone(parse_hex_rgb(junk), junk)

    def test_ctk_safe_color_never_returns_none(self):
        self.assertEqual(ctk_safe_color(None), "transparent")
        self.assertEqual(ctk_safe_color((None, "#1E2328")), ("transparent", "#1E2328"))
        self.assertEqual(ctk_safe_color((None, None)), ("transparent", "transparent"))
        self.assertEqual(ctk_safe_color("#C8AA6E"), "#C8AA6E")

    def test_lighten_invalid_color_does_not_raise(self):
        self.assertEqual(lighten_color("invalid", 10), "invalid")
        self.assertEqual(darken_color("#canvas", 10), "#canvas")
        self.assertEqual(interpolate_color("invalid", "#ffffff", 0.5), "invalid")


class TestFocusStates(unittest.TestCase):
    def test_apply_focus_ring(self):
        widget = MagicMock()
        widget.cget.side_effect = lambda key: 0 if key == "border_width" else "transparent"
        widget.master = None
        widget.winfo_exists.return_value = True
        widget.winfo_children.return_value = []
        # Pre-initialize the attributes that will be set by apply_focus_ring
        widget._orig_border_width = 0
        widget._orig_border_color = "transparent"
        
        apply_focus_ring(widget, color="#C8AA6E", width=3)
        widget.bind.assert_called()

    def test_scroll_to_widget(self):
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
        canvas.yview_moveto.assert_called()


class TestSmoothScroll(unittest.TestCase):
    def setUp(self):
        self.mock_frame = MagicMock()
        self.mock_canvas = MagicMock()
        self.mock_frame._parent_canvas = self.mock_canvas
        self.mock_canvas.winfo_exists.return_value = True
        self.mock_canvas.yview.return_value = (0.2, 0.8)
        self.mock_child = MagicMock()
        self.mock_child.winfo_children.return_value = []
        self.mock_frame.winfo_children.return_value = [self.mock_child]

    def test_apply_smooth_scroll_binding(self):
        apply_smooth_scroll(self.mock_frame, speed=0.02, decay=0.85)
        self.mock_frame.bind.assert_called_with("<MouseWheel>", unittest.mock.ANY, add="+")
        self.assertTrue(hasattr(self.mock_frame, '_smooth_scroll_state'))

    def test_mousewheel_triggers_scroll(self):
        apply_smooth_scroll(self.mock_frame, speed=0.02, decay=0.85)
        handler = self.mock_frame.bind.call_args[0][1]
        mock_event = MagicMock()
        mock_event.delta = -120
        handler(mock_event)
        state = self.mock_frame._smooth_scroll_state
        self.assertAlmostEqual(state["velocity"], 0.017, places=3)


class TestUIKwargs(unittest.TestCase):
    def setUp(self):
        self.root = MagicMock()
        self.config_mock = MagicMock()
        self.config_mock.get.return_value = {}
        self.assets_mock = MagicMock()

    def test_priority_grid_instantiation(self):
        from ui.components.priority_grid import PriorityIconGrid
        grid = PriorityIconGrid(self.root, self.config_mock, self.assets_mock)
        self.assertIsNotNone(grid)

    def test_factory_make_input(self):
        from ui.components.factory import make_input, parse_border
        entry = make_input(self.root, placeholder="Test", cursor="hand2")
        self.assertIsNotNone(entry)
        
        # Test parse_border with invalid/missing token
        w, c = parse_border("nonexistent_border_key")
        self.assertEqual(w, 0)
        self.assertEqual(c, "transparent")

    def test_factory_make_input_focus_unfocus(self):
        from ui.components.factory import make_input
        # Mock CTkEntry
        with patch('customtkinter.CTkEntry') as mock_ctk_entry:
            mock_instance = MagicMock()
            mock_ctk_entry.return_value = mock_instance
            entry = make_input(self.root, placeholder="Test", border_color=None, fg_color=None)
            self.assertIsNotNone(entry)
            
            # Find the FocusIn and FocusOut callbacks
            focus_in_cb = None
            focus_out_cb = None
            for call in mock_instance.bind.call_args_list:
                args = call[0]
                if args[0] == "<FocusIn>":
                    focus_in_cb = args[1]
                elif args[0] == "<FocusOut>":
                    focus_out_cb = args[1]

            self.assertIsNotNone(focus_in_cb)
            self.assertIsNotNone(focus_out_cb)

            # Trigger callbacks to ensure configure is called with non-None colors
            focus_in_cb(MagicMock())
            mock_instance.configure.assert_called()
            
            focus_out_cb(MagicMock())
            # Ensure border_color is not None in kwargs
            last_configure_kwargs = mock_instance.configure.call_args[1]
            self.assertIsNotNone(last_configure_kwargs.get("border_color"))
            self.assertIsNotNone(last_configure_kwargs.get("fg_color"))
            self.assertNotEqual(last_configure_kwargs.get("border_color"), None)

    def test_factory_make_input_tuple_none_border_is_sanitized(self):
        from ui.components.factory import make_input
        with patch("customtkinter.CTkEntry") as mock_ctk_entry:
            mock_instance = MagicMock()
            mock_ctk_entry.return_value = mock_instance
            make_input(self.root, border_color=(None, "#1E2328"), fg_color=(None, "#091428"))
            ctor_kwargs = mock_ctk_entry.call_args[1]
            self.assertEqual(ctor_kwargs["border_color"], ("transparent", "#1E2328"))
            self.assertEqual(ctor_kwargs["fg_color"], ("#091428", "#091428"))

            focus_out_cb = None
            for call in mock_instance.bind.call_args_list:
                if call[0][0] == "<FocusOut>":
                    focus_out_cb = call[0][1]
            self.assertIsNotNone(focus_out_cb)
            focus_out_cb(MagicMock())
            last = mock_instance.configure.call_args[1]
            self.assertNotIn(None, _flatten_color(last.get("border_color")))
            self.assertNotIn(None, _flatten_color(last.get("fg_color")))


def _flatten_color(color):
    if isinstance(color, (tuple, list)):
        return list(color)
    return [color]


if __name__ == '__main__':

    unittest.main()
