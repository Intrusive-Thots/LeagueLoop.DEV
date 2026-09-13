"""
Unit tests for DebugTracker service.
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from services.debug_tracker import DebugTracker


class TestDebugTracker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {"debug_mode": False}
        self.tracker = DebugTracker(self.config)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_disabled_by_default(self):
        """When debug_mode is False, actions should not be recorded or screenshotted."""
        result = self.tracker.record_action("test_action", "outcome_ok")
        self.assertFalse(result["recorded"])
        self.assertEqual(result["reason"], "debug_mode_disabled")

    @patch("services.debug_tracker.get_data_dir")
    @patch("PIL.ImageGrab.grab")
    def test_record_action_when_enabled(self, mock_grab, mock_get_data_dir):
        """When debug_mode is True, action details are logged to disk and screenshot is captured."""
        mock_get_data_dir.return_value = self.temp_dir
        mock_image = MagicMock()
        mock_grab.return_value = mock_image

        self.config["debug_mode"] = True
        result = self.tracker.record_action(
            action_name="fix_ping",
            outcome="MTU 1428 set",
            details={"mtu": 1428, "dns": "1.1.1.1"},
        )

        self.assertTrue(result["recorded"])
        self.assertIsNotNone(result["screenshot"])
        self.assertTrue(os.path.exists(result["log_file"]))

        # Verify screenshot save call
        mock_image.save.assert_called_once()
        self.assertTrue(mock_image.save.call_args[0][0].endswith(".png"))

        # Verify JSON log file contents
        with open(result["log_file"], "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["action"], "fix_ping")
            self.assertEqual(entry["outcome"], "MTU 1428 set")
            self.assertEqual(entry["details"]["mtu"], 1428)

    @patch("services.debug_tracker.get_data_dir")
    @patch("PIL.ImageGrab.grab")
    def test_capture_screenshot_with_window_bbox(self, mock_grab, mock_get_data_dir):
        """When a window widget is passed, bounding box is passed to ImageGrab.grab."""
        mock_get_data_dir.return_value = self.temp_dir
        mock_img = MagicMock()
        mock_grab.return_value = mock_img

        mock_window = MagicMock()
        mock_window.winfo_toplevel.return_value = mock_window
        mock_window.winfo_rootx.return_value = 100
        mock_window.winfo_rooty.return_value = 150
        mock_window.winfo_width.return_value = 800
        mock_window.winfo_height.return_value = 600

        self.config["debug_mode"] = True
        shot = self.tracker.capture_screenshot(window=mock_window, action_slug="test_slug")

        self.assertIsNotNone(shot)
        mock_grab.assert_called_once_with(bbox=(100, 150, 900, 750))


if __name__ == "_main__":
    unittest.main()
