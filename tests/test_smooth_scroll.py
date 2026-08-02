import sys
import unittest
from unittest.mock import MagicMock, patch

# Headless mock setup for CustomTkinter & Tkinter
mods_to_mock = {
    'customtkinter': MagicMock(),
    'tkinter': MagicMock(),
}
patch.dict(sys.modules, mods_to_mock).start()

from utils.smooth_scroll import apply_smooth_scroll

class TestSmoothScroll(unittest.TestCase):

    def setUp(self):
        self.mock_frame = MagicMock()
        self.mock_canvas = MagicMock()
        self.mock_frame._parent_canvas = self.mock_canvas
        self.mock_canvas.winfo_exists.return_value = True
        self.mock_canvas.yview.return_value = (0.2, 0.8)

        # Mock child widgets for recursive binding
        self.mock_child1 = MagicMock()
        self.mock_child2 = MagicMock()
        self.mock_child1.winfo_children.return_value = []
        self.mock_child2.winfo_children.return_value = []
        self.mock_frame.winfo_children.return_value = [self.mock_child1, self.mock_child2]

    def test_apply_smooth_scroll_binding(self):
        """Test that apply_smooth_scroll attaches mousewheel handlers recursively."""
        apply_smooth_scroll(self.mock_frame, speed=0.02, decay=0.85)

        self.mock_frame.bind.assert_called_with("<MouseWheel>", unittest.mock.ANY, add="+")
        self.mock_child1.bind.assert_called_with("<MouseWheel>", unittest.mock.ANY, add="+")
        self.mock_child2.bind.assert_called_with("<MouseWheel>", unittest.mock.ANY, add="+")

        self.assertTrue(hasattr(self.mock_frame, '_smooth_scroll_bind'))
        self.assertTrue(hasattr(self.mock_frame, '_smooth_scroll_state'))
        self.assertEqual(self.mock_frame._smooth_scroll_state["velocity"], 0.0)
        self.assertFalse(self.mock_frame._smooth_scroll_state["animating"])

    def test_mousewheel_event_triggers_scroll(self):
        """Test mousewheel event velocity calculation and animation trigger."""
        apply_smooth_scroll(self.mock_frame, speed=0.02, decay=0.85)

        # Retrieve the bound mousewheel handler
        handler = self.mock_frame.bind.call_args[0][1]

        mock_event = MagicMock()
        mock_event.delta = -120  # Scroll down 1 tick (delta = 1.0)

        # Trigger mousewheel input pass
        handler(mock_event)

        state = self.mock_frame._smooth_scroll_state
        # 1.0 * 0.02 = 0.02 added to velocity.
        # First animation tick decays velocity by 0.85 (0.02 * 0.85 = 0.017)
        self.assertAlmostEqual(state["velocity"], 0.017)

        # Canvas yview_moveto should have been invoked with new position (0.2 + 0.02 = 0.22)
        self.mock_canvas.yview_moveto.assert_called_once()
        new_pos = self.mock_canvas.yview_moveto.call_args[0][0]
        self.assertAlmostEqual(new_pos, 0.22)

    def test_animation_decay_and_stopping(self):
        """Test velocity decay over animation frames until velocity drops below threshold."""
        apply_smooth_scroll(self.mock_frame, speed=0.02, decay=0.5)

        state = self.mock_frame._smooth_scroll_state
        # Velocity below 0.001 on initial animation entry
        state["velocity"] = 0.0005
        state["animating"] = False

        handler = self.mock_frame.bind.call_args[0][1]
        mock_event = MagicMock()
        mock_event.delta = 0  # No scroll delta added

        handler(mock_event)

        # Velocity < 0.001 stops animation immediately and resets velocity to 0.0
        self.assertEqual(state["velocity"], 0.0)
        self.assertFalse(state["animating"])

if __name__ == '__main__':
    unittest.main()
