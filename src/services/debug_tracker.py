"""
Debug Tracker Service for LeagueLoop.
Provides Action Logging and Window Screenshot Capture when 'Debug Mode' is enabled.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Dict, Optional

from utils.logger import Logger
from utils.path_utils import get_data_dir


class DebugTracker:
    """Tracks every user/system action and captures corresponding window screenshots."""

    _instance: Optional[DebugTracker] = None

    def __init__(self, config=None):
        self.config = config

    @classmethod
    def get_instance(cls, config=None) -> DebugTracker:
        if cls._instance is None:
            cls._instance = cls(config)
        elif config is not None:
            cls._instance.config = config
        return cls._instance

    def is_enabled(self) -> bool:
        """Returns True if Debug Mode is enabled in configuration."""
        if not self.config:
            return False
        return bool(self.config.get("debug_mode", False))

    def get_debug_dir(self) -> str:
        """Directory where debug action logs are persisted."""
        path = os.path.join(get_data_dir(), "debug_logs")
        os.makedirs(path, exist_ok=True)
        return path

    def get_screenshots_dir(self) -> str:
        """Directory where debug screenshots are stored."""
        path = os.path.join(get_data_dir(), "debug_screenshots")
        os.makedirs(path, exist_ok=True)
        return path

    def capture_screenshot(self, window=None, action_slug: str = "action") -> Optional[str]:
        """
        Captures a screenshot of the application window or primary screen.
        Returns the absolute filepath of the saved screenshot, or None if unavailable.
        """
        try:
            from PIL import ImageGrab
        except ImportError:
            Logger.debug("DebugTracker", "PIL ImageGrab not available for screenshot capture")
            return None

        clean_slug = re.sub(r"[^\w\-]+", "_", action_slug.strip().lower())[:30]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{clean_slug}.png"
        filepath = os.path.join(self.get_screenshots_dir(), filename)

        # Determine bounding box if window widget is available
        bbox = None
        if window is not None:
            try:
                # Find root window if given a child widget
                toplevel = window.winfo_toplevel() if hasattr(window, "winfo_toplevel") else window
                toplevel.update_idletasks()
                rx = toplevel.winfo_rootx()
                ry = toplevel.winfo_rooty()
                rw = toplevel.winfo_width()
                rh = toplevel.winfo_height()
                if rw > 10 and rh > 10:
                    bbox = (rx, ry, rx + rw, ry + rh)
            except Exception as exc:
                Logger.debug("DebugTracker", f"Could not compute window bbox: {exc}")

        try:
            if bbox:
                img = ImageGrab.grab(bbox=bbox)
            else:
                img = ImageGrab.grab()

            img.save(filepath, "PNG")
            Logger.info("DebugTracker", f"Debug screenshot saved: {filepath}")
            return filepath
        except Exception as exc:
            Logger.debug("DebugTracker", f"Screenshot capture failed: {exc}")
            return None

    def record_action(
        self,
        action_name: str,
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
        window=None,
    ) -> Dict[str, Any]:
        """
        Logs an action, its outcome, and captures a program screenshot if Debug Mode is enabled.
        """
        if not self.is_enabled():
            return {"recorded": False, "reason": "debug_mode_disabled"}

        screenshot_path = self.capture_screenshot(window=window, action_slug=action_name)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        entry = {
            "timestamp": now_str,
            "action": action_name,
            "outcome": outcome,
            "details": details or {},
            "screenshot": screenshot_path or "None",
        }

        log_file = os.path.join(self.get_debug_dir(), "debug_actions.log")
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            Logger.error("DebugTracker", f"Failed to write to debug log: {exc}")

        Logger.action("DebugTracker", f"[{action_name}] -> {outcome}", screenshot=screenshot_path)

        return {
            "recorded": True,
            "screenshot": screenshot_path,
            "log_file": log_file,
            "entry": entry,
        }
