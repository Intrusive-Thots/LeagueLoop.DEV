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
        DebugTracker._instance = None
        self.tracker = DebugTracker(self.config)

    def tearDown(self):
        DebugTracker._instance = None
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_disabled_by_default(self):
        """When debug_mode is False, actions should not be recorded or screenshotted."""
        result = self.tracker.record_action("test_action", "outcome_ok")
        self.assertFalse(result["recorded"])
        self.assertEqual(result["reason"], "debug_mode_disabled")

    @patch("services.debug_tracker.get_data_dir")
    @patch("PIL.ImageGrab.grab")
    def test_record_action_when_enabled(self, mock_grab, mock_get_data_dir):
        """When debug_mode is True, action details are logged to disk and paired screenshot is captured."""
        from PIL import Image
        mock_get_data_dir.return_value = self.temp_dir
        mock_grab.return_value = Image.new("RGB", (400, 300), (20, 20, 20))

        self.config["debug_mode"] = True
        result = self.tracker.record_action(
            action_name="fix_ping",
            outcome="MTU 1428 set",
            details={"mtu": 1428, "dns": "1.1.1.1"},
        )

        self.assertTrue(result["recorded"])
        self.assertIsNotNone(result["screenshot"])
        self.assertTrue(os.path.exists(result["screenshot"]))
        self.assertTrue(os.path.exists(result["log_file"]))

        # Verify JSON log file contents
        with open(result["log_file"], "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["action"], "fix_ping")
            self.assertEqual(entry["outcome"], "MTU 1428 set")
            self.assertEqual(entry["details"]["mtu"], 1428)

    @patch("services.debug_tracker.get_data_dir")
    @patch("services.client_window_tracker.ClientWindowTracker.tick")
    @patch("PIL.ImageGrab.grab")
    def test_paired_screenshot_with_client_window(self, mock_grab, mock_tick, mock_get_data_dir):
        """When League Client window is visible, composite pairs both windows in the same screenshot."""
        from PIL import Image
        from services.client_window_tracker import ClientWindow
        mock_get_data_dir.return_value = self.temp_dir

        mock_tick.return_value = ClientWindow(
            found=True,
            visible=True,
            minimized=False,
            rect=(100, 100, 1280, 720),
            hwnd=12345,
            title="League of Legends",
        )

        prog_img = Image.new("RGB", (320, 500), (30, 40, 50))
        client_img = Image.new("RGB", (1280, 720), (10, 20, 30))
        mock_grab.side_effect = [prog_img, client_img]

        self.config["debug_mode"] = True
        shot = self.tracker.capture_screenshot(window=None, action_slug="dual_test", outcome="Success")

        self.assertIsNotNone(shot)
        self.assertTrue(os.path.exists(shot))

        # Check saved composite image dimensions encompass both windows
        with Image.open(shot) as saved:
            self.assertGreater(saved.width, 1280)
            self.assertGreater(saved.height, 500)

    @patch("services.debug_tracker.get_data_dir")
    @patch("PIL.ImageGrab.grab")
    def test_capture_screenshot_with_window_bbox(self, mock_grab, mock_get_data_dir):
        """When a window widget is passed, bounding box is extracted and passed to ImageGrab.grab."""
        from PIL import Image
        mock_get_data_dir.return_value = self.temp_dir
        mock_grab.return_value = Image.new("RGB", (300, 400), (20, 30, 40))

        mock_window = MagicMock()
        mock_window.winfo_toplevel.return_value = mock_window
        mock_window.winfo_id.side_effect = Exception("No hwnd in mock")
        mock_window.winfo_rootx.return_value = 100
        mock_window.winfo_rooty.return_value = 150
        mock_window.winfo_width.return_value = 800
        mock_window.winfo_height.return_value = 600

        self.config["debug_mode"] = True
        shot = self.tracker.capture_screenshot(window=mock_window, action_slug="test_slug")

        self.assertIsNotNone(shot)
        self.assertTrue(os.path.exists(shot))
        # Ensure the first call to ImageGrab.grab used bbox
        first_call = mock_grab.call_args_list[0]
        self.assertEqual(first_call.kwargs.get("bbox"), (100, 150, 900, 750))

    @patch("services.debug_tracker.get_data_dir")
    @patch("PIL.ImageGrab.grab")
    def test_config_manager_toggle_logged_in_debug_mode(self, mock_grab, mock_get_data_dir):
        """When a config toggle or setting is changed, DebugTracker logs it and captures screenshot."""
        from PIL import Image
        from services.config_manager import ConfigManager
        mock_get_data_dir.return_value = self.temp_dir
        mock_grab.return_value = Image.new("RGB", (300, 400), (20, 30, 40))

        cfg = ConfigManager()
        cfg.cfg["debug_mode"] = True
        DebugTracker.get_instance(cfg)

        # Trigger setting change on a controlled test key
        cfg.cfg["test_unit_toggle"] = False
        cfg.set("test_unit_toggle", True, save=False)

        # Verify log file has action
        tracker = DebugTracker.get_instance()
        log_file = os.path.join(tracker.get_debug_dir(), "debug_actions.log")
        self.assertTrue(os.path.exists(log_file))

        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertTrue(any("toggle:test_unit_toggle" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
