"""
Unit tests for src/utils/focus_states.py
"""

import unittest
from unittest.mock import MagicMock, patch
import customtkinter as ctk

import utils.focus_states as focus_states


class TestFocusStates(unittest.TestCase):

    def setUp(self):
        focus_states._FOCUS_COLOR = None

    def tearDown(self):
        focus_states._FOCUS_COLOR = None

    @patch("utils.focus_states.get_color", return_value="#C8AA6E")
    def test_get_focus_color_lazy_loading(self, mock_get_color):
        color1 = focus_states._get_focus_color()
        self.assertEqual(color1, "#C8AA6E")
        mock_get_color.assert_called_once_with("colors.accent.gold", "#C8AA6E")

        # Second call should use cached value without calling get_color again
        color2 = focus_states._get_focus_color()
        self.assertEqual(color2, "#C8AA6E")
        self.assertEqual(mock_get_color.call_count, 1)

    def test_apply_focus_ring_default_color_and_bindings(self):
        widget = MagicMock()
        widget.cget.side_effect = lambda attr: 1 if attr == "border_width" else "#101010"
        del widget._orig_border_width
        del widget._orig_border_color

        with patch("utils.focus_states._get_focus_color", return_value="#GOLD"):
            focus_states.apply_focus_ring(widget)

        self.assertEqual(widget._orig_border_width, 1)
        self.assertEqual(widget._orig_border_color, "#101010")

        # Check event bindings
        bind_calls = widget.bind.call_args_list
        bound_events = [call[0][0] for call in bind_calls]
        self.assertIn("<FocusIn>", bound_events)
        self.assertIn("<FocusOut>", bound_events)

        # Retrieve callbacks
        focus_in_cb = next(call[0][1] for call in bind_calls if call[0][0] == "<FocusIn>")
        focus_out_cb = next(call[0][1] for call in bind_calls if call[0][0] == "<FocusOut>")

        # Trigger focus in
        focus_in_cb(MagicMock())
        widget.configure.assert_called_with(border_width=2, border_color="#GOLD")

        # Trigger focus out
        focus_out_cb(MagicMock())
        widget.configure.assert_called_with(border_width=1, border_color="#101010")

    def test_apply_focus_ring_cget_exception_fallback(self):
        widget = MagicMock()
        widget.cget.side_effect = Exception("cget error")
        del widget._orig_border_width
        del widget._orig_border_color

        focus_states.apply_focus_ring(widget, color="#FF0000", width=3)

        self.assertEqual(widget._orig_border_width, 0)
        self.assertEqual(widget._orig_border_color, "transparent")

    def test_apply_focus_ring_callbacks_suppress_exceptions(self):
        widget = MagicMock()
        widget.cget.return_value = 0
        del widget._orig_border_width
        del widget._orig_border_color

        focus_states.apply_focus_ring(widget)

        bind_calls = widget.bind.call_args_list
        focus_in_cb = next(call[0][1] for call in bind_calls if call[0][0] == "<FocusIn>")
        focus_out_cb = next(call[0][1] for call in bind_calls if call[0][0] == "<FocusOut>")

        widget.configure.side_effect = Exception("configure failed")

        with patch("utils.focus_states.Logger.debug") as mock_log:
            focus_in_cb(MagicMock())
            mock_log.assert_called()

        with patch("utils.focus_states.Logger.debug") as mock_log:
            focus_out_cb(MagicMock())
            mock_log.assert_called()

    def test_apply_focus_ring_takefocus_branches(self):
        # Branch 1: widget._canvas.configure
        widget_canvas = MagicMock()
        del widget_canvas.tk
        del widget_canvas._w
        widget_canvas._canvas = MagicMock()
        del widget_canvas._canvas._orig_border_width
        del widget_canvas._canvas._orig_border_color
        focus_states.apply_focus_ring(widget_canvas)
        widget_canvas._canvas.configure.assert_called_with(takefocus=True)

        # Branch 2: widget.tk.call
        widget_tk = MagicMock(spec=["tk", "_w", "cget", "bind"])
        widget_tk.tk = MagicMock()
        widget_tk._w = ".widget_path"
        widget_tk.cget.return_value = 0
        focus_states.apply_focus_ring(widget_tk)
        widget_tk.tk.call.assert_called_with(".widget_path", "configure", "-takefocus", 1)

        # Branch 3: fallback widget.configure(takefocus=True)
        widget_simple = MagicMock(spec=["configure", "cget", "bind"])
        widget_simple.cget.return_value = 0
        focus_states.apply_focus_ring(widget_simple)
        widget_simple.configure.assert_called_with(takefocus=True)

        # Exception suppression during takefocus set
        widget_err = MagicMock(spec=["configure", "cget", "bind"])
        widget_err.cget.return_value = 0
        widget_err.configure.side_effect = Exception("takefocus error")
        with patch("utils.focus_states.Logger.debug") as mock_log:
            focus_states.apply_focus_ring(widget_err)
            mock_log.assert_called()

    def test_scroll_to_widget_canvas_not_exists(self):
        scrollable_frame = MagicMock()
        canvas = MagicMock()
        canvas.winfo_exists.return_value = False
        scrollable_frame._parent_canvas = canvas

        widget = MagicMock()
        focus_states.scroll_to_widget(scrollable_frame, widget)
        canvas.yview_moveto.assert_not_called()

    def test_scroll_to_widget_invalid_visible_fraction(self):
        scrollable_frame = MagicMock()
        canvas = MagicMock()
        canvas.winfo_exists.return_value = True
        canvas.yview.return_value = (0.0, 1.0)  # fraction = 1.0 >= 1.0
        scrollable_frame._parent_canvas = canvas

        widget = MagicMock()
        focus_states.scroll_to_widget(scrollable_frame, widget)
        canvas.yview_moveto.assert_not_called()

    def test_scroll_to_widget_scroll_up(self):
        scrollable_frame = MagicMock()
        canvas = MagicMock()
        del canvas.yview
        canvas.yview = MagicMock(return_value=(0.2, 0.6))  # visible fraction = 0.4, total_height = 1000
        canvas.winfo_exists.return_value = True
        canvas.winfo_rooty.return_value = 200
        canvas.winfo_height.return_value = 400
        scrollable_frame._parent_canvas = canvas

        widget = MagicMock()
        widget.winfo_rooty.return_value = 100  # Above canvas rooty (200) -> scroll_pixels = -100
        widget.winfo_height.return_value = 50

        focus_states.scroll_to_widget(scrollable_frame, widget)
        # fraction_diff = -100 / 1000 = -0.1
        # new_y = 0.2 + (-0.1) = 0.1
        canvas.yview_moveto.assert_called_once()
        args, _ = canvas.yview_moveto.call_args
        self.assertAlmostEqual(args[0], 0.1, places=5)

    def test_scroll_to_widget_scroll_down(self):
        scrollable_frame = MagicMock()
        canvas = MagicMock()
        del canvas.yview
        canvas.yview = MagicMock(return_value=(0.0, 0.5))  # visible fraction = 0.5, total_height = 600
        canvas.winfo_exists.return_value = True
        canvas.winfo_rooty.return_value = 100
        canvas.winfo_height.return_value = 300
        scrollable_frame._parent_canvas = canvas

        widget = MagicMock()
        widget.winfo_rooty.return_value = 350  # w_y (350) + w_h (100) = 450 > c_y (100) + c_h (300) = 400
        widget.winfo_height.return_value = 100  # scroll_pixels = 450 - 400 = 50

        focus_states.scroll_to_widget(scrollable_frame, widget)
        # fraction_diff = 50 / 600 = 0.08333...
        # new_y = 0.0 + 0.08333 = 0.08333333333333333
        canvas.yview_moveto.assert_called_once()
        args, _ = canvas.yview_moveto.call_args
        self.assertAlmostEqual(args[0], 0.0833333, places=5)

    def test_scroll_to_widget_exception_suppression(self):
        scrollable_frame = MagicMock()
        scrollable_frame._parent_canvas.winfo_exists.side_effect = Exception("Canvas fail")
        widget = MagicMock()

        with patch("utils.focus_states.Logger.debug") as mock_log:
            focus_states.scroll_to_widget(scrollable_frame, widget)
            mock_log.assert_called()

    def test_apply_focus_states_recursive(self):
        container = MagicMock()

        class DummyButton(ctk.CTkButton):
            def __init__(self):
                self.master = None
                self.winfo_exists = MagicMock(return_value=False)
                self.winfo_children = MagicMock(return_value=[])
                self.bind = MagicMock()

        class DummyEntry(ctk.CTkEntry):
            def __init__(self):
                self.master = None
                self.winfo_exists = MagicMock(return_value=False)
                self.winfo_children = MagicMock(return_value=[])
                self.bind = MagicMock()

        class LolToggle:
            def __init__(self):
                self.master = None
                self.winfo_exists = MagicMock(return_value=False)
                self.winfo_children = MagicMock(return_value=[])
                self.bind = MagicMock()

        button = DummyButton()
        entry = DummyEntry()
        toggle = LolToggle()

        container.winfo_exists.return_value = True
        container.winfo_children.return_value = [button, entry, toggle]

        with patch("utils.focus_states.apply_focus_ring") as mock_apply_ring:
            focus_states.apply_focus_states_recursive(container, skip_types={"DummyEntry"})

            # DummyButton should have focus ring applied, DummyEntry skipped due to skip_types
            mock_apply_ring.assert_called_once_with(button)

        # Test scroll-to-view callback on focus event
        button_bind_calls = button.bind.call_args_list
        focus_scroll_cb = next(call[0][1] for call in button_bind_calls if call[0][0] == "<FocusIn>")

        # Event for different widget -> should do nothing
        other_event = MagicMock()
        other_event.widget = MagicMock()
        focus_scroll_cb(other_event)

        # Event for button inside a CTkScrollableFrame ancestor
        scrollable = MagicMock(spec=ctk.CTkScrollableFrame)
        scrollable.master = None
        parent_frame = MagicMock()
        parent_frame.master = scrollable
        button.master = parent_frame

        button_event = MagicMock()
        button_event.widget = button

        with patch("utils.focus_states.scroll_to_widget") as mock_scroll:
            focus_scroll_cb(button_event)
            mock_scroll.assert_called_once_with(scrollable, button)


if __name__ == "__main__":
    unittest.main()
