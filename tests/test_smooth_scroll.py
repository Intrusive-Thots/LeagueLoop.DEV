import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock customtkinter before importing smooth_scroll if needed
mods_to_mock = {
    'customtkinter': MagicMock(),
    'tkinter': MagicMock(),
}

with patch.dict(sys.modules, mods_to_mock):
    from utils.smooth_scroll import apply_smooth_scroll


class TestSmoothScroll(unittest.TestCase):
    def setUp(self):
        self.frame = MagicMock()
        self.canvas = MagicMock()
        self.frame._parent_canvas = self.canvas
        self.frame.winfo_exists.return_value = True
        self.canvas.winfo_exists.return_value = True
        self.canvas.yview.return_value = (0.2, 0.8)

        self.child1 = MagicMock()
        self.child2 = MagicMock()
        self.child1.winfo_children.return_value = [self.child2]
        self.child2.winfo_children.return_value = []
        self.frame.winfo_children.return_value = [self.child1]

    def test_apply_smooth_scroll_binds_recursively_and_attaches_state(self):
        apply_smooth_scroll(self.frame, speed=0.02, decay=0.85)

        # Check binding on main frame and children
        self.frame.bind.assert_called_with("<MouseWheel>", unittest.mock.ANY, add="+")
        self.child1.bind.assert_called_with("<MouseWheel>", unittest.mock.ANY, add="+")
        self.child2.bind.assert_called_with("<MouseWheel>", unittest.mock.ANY, add="+")

        # Check attached state and re-bind function
        self.assertTrue(hasattr(self.frame, "_smooth_scroll_state"))
        self.assertTrue(hasattr(self.frame, "_smooth_scroll_bind"))
        self.assertEqual(self.frame._smooth_scroll_state["velocity"], 0.0)
        self.assertFalse(self.frame._smooth_scroll_state["animating"])

    def test_mousewheel_event_updates_velocity_and_triggers_animation(self):
        apply_smooth_scroll(self.frame, speed=0.02, decay=0.85)

        # Get the handler bound to MouseWheel
        handler = self.frame.bind.call_args[0][1]

        event = MagicMock()
        event.delta = -120  # Scroll down
        handler(event)

        state = self.frame._smooth_scroll_state
        # delta = -(-120) / 120 = 1.0; velocity = 1.0 * 0.02 = 0.02
        # After initial animate_scroll run, yview_moveto is called and decay is applied once
        # velocity = 0.02 * 0.85 = 0.017
        self.assertAlmostEqual(state["velocity"], 0.017, places=4)
        self.assertTrue(state["animating"])
        self.canvas.yview_moveto.assert_called_once_with(0.22)
        self.frame.after.assert_called_once_with(16, unittest.mock.ANY)

    def test_mousewheel_upward_scroll(self):
        apply_smooth_scroll(self.frame, speed=0.05, decay=0.8)

        handler = self.frame.bind.call_args[0][1]
        event = MagicMock()
        event.delta = 120  # Scroll up -> delta = -1.0 * 0.05 = -0.05
        handler(event)

        # current[0] = 0.2, new_pos = 0.2 - 0.05 = 0.15
        self.assertEqual(self.canvas.yview_moveto.call_count, 1)
        actual_pos = self.canvas.yview_moveto.call_args[0][0]
        self.assertAlmostEqual(actual_pos, 0.15, places=4)

    def test_position_clamping_upper_and_lower_bounds(self):
        # Upper bound test
        self.canvas.yview.return_value = (0.95, 1.0)
        apply_smooth_scroll(self.frame, speed=0.1, decay=0.85)
        handler = self.frame.bind.call_args[0][1]

        event = MagicMock()
        event.delta = -240  # velocity += 0.2 -> new_pos 1.15 -> clamped to 1.0
        handler(event)

        self.canvas.yview_moveto.assert_called_once_with(1.0)

        # Reset mocks for lower bound test
        self.canvas.reset_mock()
        self.frame.reset_mock()
        self.canvas.yview.return_value = (0.02, 0.5)

        apply_smooth_scroll(self.frame, speed=0.1, decay=0.85)
        handler = self.frame.bind.call_args[0][1]

        event = MagicMock()
        event.delta = 240  # velocity += -0.2 -> new_pos -0.18 -> clamped to 0.0
        handler(event)

        self.canvas.yview_moveto.assert_called_once_with(0.0)

    def test_animation_stops_when_velocity_below_threshold(self):
        apply_smooth_scroll(self.frame, speed=0.0005, decay=0.85)
        handler = self.frame.bind.call_args[0][1]

        event = MagicMock()
        event.delta = -120  # velocity += 0.0005 < 0.001
        handler(event)

        state = self.frame._smooth_scroll_state
        self.assertEqual(state["velocity"], 0.0)
        self.assertFalse(state["animating"])
        self.canvas.yview_moveto.assert_not_called()
        self.frame.after.assert_not_called()

    def test_animation_stops_if_frame_does_not_exist(self):
        apply_smooth_scroll(self.frame, speed=0.02, decay=0.85)
        handler = self.frame.bind.call_args[0][1]

        self.frame.winfo_exists.return_value = False

        event = MagicMock()
        event.delta = -120
        handler(event)

        state = self.frame._smooth_scroll_state
        self.assertFalse(state["animating"])
        self.canvas.yview_moveto.assert_not_called()

    def test_animation_stops_if_canvas_does_not_exist(self):
        apply_smooth_scroll(self.frame, speed=0.02, decay=0.85)
        handler = self.frame.bind.call_args[0][1]

        self.canvas.winfo_exists.return_value = False

        event = MagicMock()
        event.delta = -120
        handler(event)

        state = self.frame._smooth_scroll_state
        self.assertFalse(state["animating"])
        self.canvas.yview_moveto.assert_not_called()

    def test_animation_stops_on_canvas_yview_exception(self):
        apply_smooth_scroll(self.frame, speed=0.02, decay=0.85)
        handler = self.frame.bind.call_args[0][1]

        self.canvas.yview.side_effect = RuntimeError("Canvas error")

        event = MagicMock()
        event.delta = -120
        handler(event)

        state = self.frame._smooth_scroll_state
        self.assertFalse(state["animating"])

    def test_animation_stops_on_after_scheduling_exception(self):
        apply_smooth_scroll(self.frame, speed=0.02, decay=0.85)
        handler = self.frame.bind.call_args[0][1]

        self.frame.after.side_effect = RuntimeError("After error")

        event = MagicMock()
        event.delta = -120
        handler(event)

        state = self.frame._smooth_scroll_state
        self.assertFalse(state["animating"])

    def test_rebind_functionality(self):
        apply_smooth_scroll(self.frame, speed=0.02, decay=0.85)

        new_child = MagicMock()
        new_child.winfo_children.return_value = []

        self.frame._smooth_scroll_bind(new_child)
        new_child.bind.assert_called_once_with("<MouseWheel>", unittest.mock.ANY, add="+")


if __name__ == "__main__":
    unittest.main()
