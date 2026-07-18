"""
Window Manager Mixin
────────────────────
Extracted from main.py — handles Win32 docking, window state management,
dragging, minimize/restore sync, and the docking loop.
"""
import ctypes
import ctypes.wintypes
import time

import psutil

from utils.logger import Logger
from core.constants import (
    DOCKING_POLL_INTERVAL, DOCKING_IDLE_INTERVAL, GEOMETRY_THRESHOLD,
)

_SET_WINDOW_LONG = None
if hasattr(ctypes, "windll"):
    _SET_WINDOW_LONG = getattr(ctypes.windll.user32, "SetWindowLongPtrW",
                               getattr(ctypes.windll.user32, "SetWindowLongW", None))


class WindowManagerMixin:
    """Mixin providing window docking, dragging, and state management for LeagueLoopApp."""

    def _handle_window_service_state(self, action):
        """Callback from WindowService to change CTk window state."""
        if action == "minimize":
            self.after(0, lambda: self._handle_window_state("minimize"))
            self._is_minimized_by_sync = True
        elif action == "restore":
            self.after(0, lambda: self._handle_window_state("restore"))
            self._is_minimized_by_sync = False
        elif action == "topmost_on":
            self.after(0, lambda: self.attributes("-topmost", True))
        elif action == "topmost_off":
            self.after(0, lambda: self.attributes("-topmost", False))

    def _on_close_request(self):
        """Intercept X button. Hide to tray if enabled, otherwise quit."""
        if self.config.get("run_in_tray", True):
            self._manually_hidden = True
            self.withdraw()
            if not self.tray._is_running:
                self.tray.start()
        else:
            self.destroy()

    def show_from_tray(self):
        """Restore the window from system tray and reset manual hide flag."""
        self._manually_hidden = False
        self._is_minimized_by_sync = False
        self.deiconify()
        self.app_root.lift() if hasattr(self, "app_root") else self.lift()
        self.app_root.focus_force() if hasattr(self, "app_root") else self.focus_force()

    def _setup_window_dragging(self):
        """Binds drag mouse events to enable moving the borderless window."""
        for widget in self.sidebar.drag_widgets:
            widget.bind("<ButtonPress-1>", self.on_drag_start)
            widget.bind("<B1-Motion>", self.on_drag_motion)

    def on_drag_start(self, event):
        """Handles drag start event."""
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def on_drag_stop(self, event):
        """Handles drag stop event."""
        pass

    def on_drag_motion(self, event):
        """Handles drag motion event."""
        x = self.winfo_x() - self._drag_data["x"] + event.x
        y = self.winfo_y() - self._drag_data["y"] + event.y
        self.geometry(f"+{x}+{y}")

    def _handle_window_state(self, state):
        if state == "minimize":
            self.attributes("-topmost", False)
            try:
                SW_MINIMIZE = 6
                hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                if hwnd == 0: hwnd = self.winfo_id()
                ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
            except Exception:
                self.withdraw()
            Logger.info("SYS", "Minimizing window.")
        elif state == "restore":
            if getattr(self, "_manually_hidden", False):
                Logger.info("SYS", "Window is manually hidden to tray, skipping restore.")
                return
            try:
                SW_RESTORE = 9
                hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                if hwnd == 0: hwnd = self.winfo_id()
                ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
            except Exception:
                pass
            self.after(0, self.deiconify)
            self.after(50, self.lift)
            Logger.info("SYS", "Restoring window.")
        elif state == "restore_quiet":
            if getattr(self, "_manually_hidden", False):
                Logger.info("SYS", "Window is manually hidden to tray, skipping restore_quiet.")
                return
            try:
                SW_SHOWNOACTIVATE = 4
                hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                if hwnd == 0: hwnd = self.winfo_id()
                ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
            except Exception:
                self.after(0, self.deiconify)
            self.attributes("-topmost", False)
            Logger.info("SYS", "Stealth restore (no focus steal).")

    def _attach_to_hwnd(self, parent_hwnd):
        """OS-level bond to League Client. Syncs minimize/restore and Z-order natively."""
        try:
            GWLP_HWNDPARENT = -8
            my_hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if my_hwnd == 0:
                my_hwnd = self.winfo_id()

            if _SET_WINDOW_LONG:
                _SET_WINDOW_LONG(my_hwnd, GWLP_HWNDPARENT, parent_hwnd)

        except Exception:
            pass

    def docking_loop(self):
        """Finds League of Legends client and clips to the right side of it."""
        last_hwnd = 0
        last_geom = (0, 0, 0, 0)
        last_topmost = None
        self._is_dock_attached = False
        self._is_minimized_by_sync = False

        _CLIENT_PROCS = {
            "leagueclientux.exe",
            "leagueclient.exe",
            "riot client.exe",
            "riotclientux.exe",
            "riotclientservices.exe",
        }

        def is_client_window(h):
            try:
                pid = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                if pid.value == 0:
                    return False
                proc = psutil.Process(pid.value)
                return proc.name().lower() in _CLIENT_PROCS
            except Exception:
                return False

        _CLIENT_TITLES = {"league of legends", "riot client"}

        def find_client_hwnd():
            try:
                target_hwnd = [0]
                def enum_callback(h, extra):
                    if not user32.IsWindowVisible(h):
                        return True
                    length = user32.GetWindowTextLengthW(h)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(h, buf, length + 1)
                        title = buf.value.lower().strip()
                        if title in _CLIENT_TITLES:
                            if is_client_window(h):
                                target_hwnd[0] = h
                                return False
                    return True
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
                user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
                return target_hwnd[0]
            except Exception:
                return 0

        def is_game_process_running():
            from utils.client_detector import is_game_running
            return is_game_running()

        while self.running and not self._stop_event.is_set():
            try:
                hwnd = 0
                windll = getattr(ctypes, "windll", None)
                user32 = getattr(windll, "user32", None) if windll else None

                if not user32:
                    time.sleep(2.0)
                    continue

                if last_hwnd != 0 and user32.IsWindow(last_hwnd) and is_client_window(last_hwnd):
                    hwnd = last_hwnd
                else:
                    hwnd = find_client_hwnd()

                if hwnd != 0:
                    if hwnd != last_hwnd or not self._is_dock_attached:
                        last_hwnd = hwnd
                        self.after(0, lambda h=hwnd: self._attach_to_hwnd(h))
                        self._is_dock_attached = True

                    is_game_active = is_game_process_running()
                    is_client_minimized = (user32.IsIconic(hwnd) != 0) or (user32.IsWindowVisible(hwnd) == 0)

                    if is_game_active:
                        if self._is_minimized_by_sync and not self._manually_hidden:
                            self.after(0, lambda: self._handle_window_state("restore"))
                            self._is_minimized_by_sync = False

                        if last_topmost is not False:
                            self.after(0, lambda: self.attributes("-topmost", False))
                            last_topmost = False
                    elif is_client_minimized:
                        if self.state() != "withdrawn" and self.state() != "iconic" and not self._is_minimized_by_sync:
                            self.after(0, lambda: self._handle_window_state("minimize"))
                            self._is_minimized_by_sync = True
                    else:
                        if self._is_minimized_by_sync and not self._manually_hidden:
                            self.after(0, lambda: self._handle_window_state("restore"))
                            self._is_minimized_by_sync = False

                        rect = ctypes.wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))

                        client_x = rect.left
                        client_y = rect.top
                        client_w = rect.right - rect.left
                        client_h = rect.bottom - rect.top

                        if client_w > 100:
                            is_expanded = getattr(self, "sidebar", None) is None or getattr(self.sidebar, "_body_expanded", True)
                            my_w = 200 if is_expanded else 44
                            my_h = client_h if is_expanded else 44
                            target_x = client_x + client_w
                            target_y = client_y

                            screen_w = self.winfo_screenwidth()
                            if target_x + my_w > screen_w:
                                target_x = client_x - my_w

                            curr_geom = (target_x, target_y, my_w, my_h)
                            if any(abs(curr_geom[i] - last_geom[i]) > GEOMETRY_THRESHOLD for i in range(4)):
                                self.after(0, lambda x=target_x, y=target_y, h=my_h: self.geometry(f"{my_w}x{h}+{x}+{y}"))
                                last_geom = curr_geom

                            fg_hwnd = user32.GetForegroundWindow()
                            my_id = user32.GetParent(self.winfo_id())
                            if my_id == 0:
                                my_id = self.winfo_id()

                            is_active = (fg_hwnd == hwnd) or (fg_hwnd == my_id)

                            if is_active != last_topmost:
                                last_topmost = is_active
                                if is_active:
                                    self.after(0, lambda: self.attributes("-alpha", 1.0))
                                    self.after(0, lambda: self.attributes("-topmost", True))
                                else:
                                    self.after(0, lambda: self.attributes("-topmost", False))

                    time.sleep(DOCKING_POLL_INTERVAL)
                else:
                    if self._is_dock_attached:
                        self.after(0, lambda: self._attach_to_hwnd(0))
                        self._is_dock_attached = False
                    last_hwnd = 0
                    last_geom = (0, 0, 0, 0)
                    last_topmost = None
                    time.sleep(DOCKING_IDLE_INTERVAL)
            except Exception as e:
                Logger.debug("SYS", f"Docking loop error: {e}")
            time.sleep(DOCKING_POLL_INTERVAL)
