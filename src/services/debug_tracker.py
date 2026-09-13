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
    _app_window: Any = None

    def __init__(self, config=None):
        self.config = config

    @classmethod
    def set_app_window(cls, window) -> None:
        """Registers the primary application window for automatic screenshot bounds."""
        cls._app_window = window

    @classmethod
    def get_app_window(cls) -> Any:
        return cls._app_window

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

    def _get_window_bbox(self, window) -> Optional[Tuple[int, int, int, int]]:
        """Computes screen bounding box (left, top, right, bottom) for a tkinter widget."""
        if window is None:
            return None

        # 1. Try Win32 API GetWindowRect on HWND if on Windows
        if sys.platform == "win32":
            try:
                import ctypes
                import ctypes.wintypes
                toplevel = window.winfo_toplevel() if hasattr(window, "winfo_toplevel") else window
                hwnd = toplevel.winfo_id()
                rect = ctypes.wintypes.RECT()
                if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    if w > 10 and h > 10:
                        return (rect.left, rect.top, rect.right, rect.bottom)
            except Exception as exc:
                Logger.debug("DebugTracker", f"Win32 GetWindowRect failed: {exc}", exc=exc)

        # 2. Fallback to Tkinter geometry coordinates
        try:
            toplevel = window.winfo_toplevel() if hasattr(window, "winfo_toplevel") else window
            toplevel.update_idletasks()
            rx = toplevel.winfo_rootx()
            ry = toplevel.winfo_rooty()
            rw = toplevel.winfo_width()
            rh = toplevel.winfo_height()
            if rw > 10 and rh > 10:
                return (rx, ry, rx + rw, ry + rh)
        except Exception as exc:
            Logger.debug("DebugTracker", f"Tkinter bbox calculation failed: {exc}", exc=exc)

        return None

    def _create_placeholder_image(self, width: int, height: int, title: str, subtitle: str):
        """Creates a styled placeholder card for when the League Client is not visible."""
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (max(width, 400), max(height, 300)), (13, 20, 32))
        draw = ImageDraw.Draw(img)

        try:
            f_title = ImageFont.truetype("arialbd.ttf", 16)
            f_sub = ImageFont.truetype("arial.ttf", 13)
        except Exception as exc:
            Logger.debug("DebugTracker", f"Default font fallback in placeholder: {exc}", exc=exc)
            f_title = ImageFont.load_default()
            f_sub = ImageFont.load_default()

        draw.rectangle([(2, 2), (img.width - 3, img.height - 3)], outline=(40, 55, 80), width=2)
        cx = img.width // 2
        cy = img.height // 2

        draw.text((cx, cy - 20), title, fill=(200, 170, 110), font=f_title, anchor="mm")
        draw.text((cx, cy + 15), subtitle, fill=(140, 160, 185), font=f_sub, anchor="mm")
        return img

    def _compose_paired_image(
        self,
        prog_img,
        client_img,
        action_name: str,
        outcome: str,
        client_title: str,
        timestamp_str: str,
    ):
        """
        Composes LeagueLoop window and League Client window side-by-side into a single image.
        """
        from PIL import Image, ImageDraw, ImageFont

        # Constrain max sizes to prevent massive memory usage or files
        if client_img.width > 1280:
            scale = 1280.0 / client_img.width
            client_img = client_img.resize((1280, int(client_img.height * scale)), Image.Resampling.LANCZOS)

        if prog_img.width > 900:
            scale = 900.0 / prog_img.width
            prog_img = prog_img.resize((900, int(prog_img.height * scale)), Image.Resampling.LANCZOS)

        margin = 14
        header_h = 44
        panel_title_h = 30

        content_h = max(prog_img.height, client_img.height)
        canvas_w = prog_img.width + client_img.width + (3 * margin)
        canvas_h = header_h + panel_title_h + content_h + (2 * margin)

        canvas = Image.new("RGB", (canvas_w, canvas_h), (11, 17, 27))
        draw = ImageDraw.Draw(canvas)

        try:
            f_header_bold = ImageFont.truetype("arialbd.ttf", 15)
            f_header = ImageFont.truetype("arial.ttf", 13)
            f_panel = ImageFont.truetype("arialbd.ttf", 13)
        except Exception as exc:
            Logger.debug("DebugTracker", f"Default font fallback in composite: {exc}", exc=exc)
            f_header_bold = ImageFont.load_default()
            f_header = ImageFont.load_default()
            f_panel = ImageFont.load_default()

        # Top Header Bar
        draw.rectangle([(0, 0), (canvas_w, header_h)], fill=(7, 12, 20))
        draw.line([(0, header_h), (canvas_w, header_h)], fill=(35, 45, 65), width=1)

        draw.text((margin, 13), "LEAGUELOOP DEBUG PAIR", fill=(200, 170, 110), font=f_header_bold)
        header_info = f"Action: {action_name}  |  Outcome: {outcome}  |  {timestamp_str}"
        draw.text((margin + 220, 14), header_info, fill=(230, 230, 230), font=f_header)

        # Left Panel (Program)
        left_x = margin
        left_y = header_h + panel_title_h
        draw.text((left_x, header_h + 8), "[PROGRAM] LeagueLoop Companion", fill=(200, 170, 110), font=f_panel)
        canvas.paste(prog_img, (left_x, left_y))
        draw.rectangle([(left_x - 1, left_y - 1), (left_x + prog_img.width, left_y + prog_img.height)], outline=(45, 60, 85), width=1)

        # Right Panel (League Client)
        right_x = left_x + prog_img.width + margin
        right_y = header_h + panel_title_h
        client_label = f"[GAME CLIENT] {client_title}" if client_title else "[GAME CLIENT] League of Legends"
        draw.text((right_x, header_h + 8), client_label, fill=(100, 200, 255), font=f_panel)
        canvas.paste(client_img, (right_x, right_y))
        draw.rectangle([(right_x - 1, right_y - 1), (right_x + client_img.width, right_y + client_img.height)], outline=(45, 60, 85), width=1)

        return canvas

    def capture_screenshot(
        self,
        window=None,
        action_slug: str = "action",
        outcome: str = "",
    ) -> Optional[str]:
        """
        Captures a composite screenshot pairing the LeagueLoop program window and the League Client.
        Returns the absolute filepath of the saved screenshot, or None if unavailable.
        """
        try:
            from PIL import ImageGrab
        except ImportError:
            Logger.debug("DebugTracker", "PIL ImageGrab not available for screenshot capture")
            return None

        clean_slug = re.sub(r"[^\w\-]+", "_", action_slug.strip().lower())[:30]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        timestamp_display = time.strftime("%Y-%m-%d %H:%M:%S")
        filename = f"{timestamp}_{clean_slug}.png"
        filepath = os.path.join(self.get_screenshots_dir(), filename)

        if window is None and self._app_window is not None:
            window = self._app_window

        # 1. Grab LeagueLoop Program Window
        prog_bbox = self._get_window_bbox(window)
        try:
            if prog_bbox:
                prog_img = ImageGrab.grab(bbox=prog_bbox)
            else:
                prog_img = ImageGrab.grab()
        except Exception as exc:
            Logger.debug("DebugTracker", f"Grabbing program window failed: {exc}", exc=exc)
            try:
                prog_img = ImageGrab.grab()
            except Exception as exc2:
                Logger.debug("DebugTracker", f"Fullscreen grab fallback failed: {exc2}", exc=exc2)
                return None

        # 2. Locate and Grab League Client Window
        client_img = None
        client_title = ""
        try:
            from services.client_window_tracker import ClientWindowTracker
            cw = ClientWindowTracker().tick()
            if cw.usable:
                client_bbox = (cw.rect[0], cw.rect[1], cw.rect[0] + cw.rect[2], cw.rect[1] + cw.rect[3])
                client_img = ImageGrab.grab(bbox=client_bbox)
                client_title = cw.title or "League of Legends"
            elif cw.found and cw.minimized:
                client_title = f"{cw.title} (Minimized)"
        except Exception as exc:
            Logger.debug("DebugTracker", f"Client window tracking failed: {exc}", exc=exc)

        # 3. If League Client not found or minimized, build informative placeholder
        if client_img is None:
            sub = "Client window not detected on screen" if not client_title else "Client window is currently minimized"
            client_img = self._create_placeholder_image(
                width=600,
                height=prog_img.height,
                title="League of Legends Client",
                subtitle=sub,
            )
            if not client_title:
                client_title = "Not Detected / Closed"

        # 4. Compose paired image
        try:
            composite = self._compose_paired_image(
                prog_img=prog_img,
                client_img=client_img,
                action_name=action_slug,
                outcome=outcome or "Executed",
                client_title=client_title,
                timestamp_str=timestamp_display,
            )
            composite.save(filepath, "PNG")
            Logger.info("DebugTracker", f"Debug paired screenshot saved: {filepath}")
            return filepath
        except Exception as exc:
            Logger.debug("DebugTracker", f"Composing paired screenshot failed: {exc}", exc=exc)
            # Fallback to single program image if compositing fails
            try:
                prog_img.save(filepath, "PNG")
                return filepath
            except Exception as exc2:
                Logger.debug("DebugTracker", f"Program image fallback save failed: {exc2}", exc=exc2)
                return None

    def record_action(
        self,
        action_name: str,
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
        window=None,
    ) -> Dict[str, Any]:
        """
        Logs an action, its outcome, and captures a paired program+client screenshot if Debug Mode is enabled.
        """
        if not self.is_enabled():
            return {"recorded": False, "reason": "debug_mode_disabled"}

        if window is None and self._app_window is not None:
            window = self._app_window

        screenshot_path = self.capture_screenshot(
            window=window,
            action_slug=action_name,
            outcome=outcome,
        )
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
