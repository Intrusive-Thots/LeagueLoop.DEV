"""
Unit tests for src/ui/components/focus_ring.py
"""

import unittest
from unittest.mock import MagicMock, patch
import customtkinter as ctk

from ui.components.focus_ring import (
    _owner,
    _activate,
    _Rings,
    make_focusable,
    install_focus_rings,
)


class TestFocusRing(unittest.TestCase):

    def test_rings_init_tolerates_iso_left_tab_tcl_error(self):
        root = MagicMock()

        def mock_bind_all(event, handler, add=None):
            if event == "<ISO_Left_Tab>":
                raise ctk.tkinter.TclError('bad event type or keysym "ISO_Left_Tab"')

        root.bind_all.side_effect = mock_bind_all

        # Should not raise exception
        rings = _Rings(root)
        self.assertFalse(rings.keyboard)
        self.assertIsNone(rings.current)

    def test_owner_mapping(self):
        btn = MagicMock(spec=ctk.CTkButton)
        inner_canvas = MagicMock(spec=["master"])
        inner_canvas.master = btn

        self.assertIs(_owner(btn), btn)
        self.assertIs(_owner(inner_canvas), btn)

        # Unrelated widget returns None
        unrelated = MagicMock(spec=["master"])
        unrelated.master = None
        self.assertIsNone(_owner(unrelated))

    def test_activate_dispatch(self):
        # Switch / checkbox with toggle
        switch = MagicMock(spec=ctk.CTkSwitch)
        _activate(switch)
        switch.toggle.assert_called_once()

        # Control with invoke
        button = MagicMock()
        del button.toggle
        button.invoke = MagicMock()
        _activate(button)
        button.invoke.assert_called_once()

        # Control with _on_click
        clickable = MagicMock()
        del clickable.toggle
        del clickable.invoke
        clickable._on_click = MagicMock()
        _activate(clickable)
        clickable._on_click.assert_called_once()

    def test_make_focusable_traversal(self):
        parent = MagicMock()
        child_btn = MagicMock(spec=ctk.CTkButton)
        child_btn.winfo_children.return_value = []
        child_canvas = MagicMock()
        child_canvas._ll_bound = False
        child_btn._canvas = child_canvas

        parent.winfo_children.return_value = [child_btn]

        count = make_focusable(parent)
        self.assertEqual(count, 1)
        child_canvas.configure.assert_called_once_with(takefocus=1)
        self.assertTrue(getattr(child_canvas, "_ll_bound", False))

    def test_install_focus_rings_idempotent(self):
        root = MagicMock()
        root._ll_rings = None
        root.winfo_children.return_value = []

        count = install_focus_rings(root)
        self.assertIsNotNone(root._ll_rings)
        self.assertEqual(count, 0)

        existing_rings = root._ll_rings
        install_focus_rings(root)
        self.assertIs(root._ll_rings, existing_rings)


if __name__ == "__main__":
    unittest.main()
