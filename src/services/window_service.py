"""
Window Service
Coordinates window docking, multi-monitor geometry adjustments, parenting, and Docked vs. Undocked states.
"""
import ctypes
import threading
import time
from core.events import EventBus
from services.settings_service import get_settings_service
from utils.logger import Logger

try:
    import ctypes.wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
except (AttributeError, ImportError):
    user32 = None
    kernel32 = None

_CLIENT_PROCS = {
    "leagueclientux.exe",
    "leagueclient.exe",
    "riot client.exe",
    "riotclientux.exe",
    "riotclientservices.exe",
}
_CLIENT_TITLES = {"league of legends", "riot client"}

class WindowService:
    def __init__(self, settings_service=None):
        self._settings = settings_service or get_settings_service()
        self._docked_mode = True
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._registered_windows = {} # hwnd -> callbacks dict
        self._client_hwnd = 0
        self._is_dock_attached = False
        self._is_minimized_by_sync = False
        
        # Load docked mode state from settings
        if self._settings:
            self._docked_mode = self._settings.get("docked_mode", True)
            
        EventBus.on("setting_changed:docked_mode", self._on_docked_mode_setting_changed)

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._window_loop, daemon=True)
            self._thread.start()
            Logger.info("WindowService", "Docking and window services started.")

    def stop(self):
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def set_docked_mode(self, enabled: bool):
        if self._docked_mode != enabled:
            self._docked_mode = enabled
            if self._settings:
                self._settings.set("docked_mode", enabled)
            Logger.info("WindowService", f"Docked mode changed to: {enabled}")
            EventBus.emit("docked_mode_changed", enabled)

    @property
    def is_docked(self) -> bool:
        return self._docked_mode

    def _on_docked_mode_setting_changed(self, enabled):
        self.set_docked_mode(enabled)

    def register_window(self, hwnd: int, geom_cb, state_cb):
        """Register a window handle with its positioning and state callbacks."""
        with self._lock:
            self._registered_windows[hwnd] = {
                "geom_cb": geom_cb,
                "state_cb": state_cb,
                "attached": False
            }
        Logger.info("WindowService", f"Registered window handle: {hwnd}")

    def unregister_window(self, hwnd: int):
        with self._lock:
            if hwnd in self._registered_windows:
                del self._registered_windows[hwnd]
        Logger.info("WindowService", f"Unregistered window handle: {hwnd}")

    def _attach_window(self, my_hwnd: int, parent_hwnd: int):
        """Set window parenting using Win32 SetWindowLongPtr or SetParent."""
        if not user32 or my_hwnd == 0:
            return
        try:
            # If parent_hwnd is 0, we clear the parenting (detach)
            if parent_hwnd == 0:
                user32.SetParent(my_hwnd, 0)
                # Reset styles (make it a normal WS_OVERLAPPED window)
                GWL_STYLE = -16
                WS_POPUP = 0x80000000
                style = user32.GetWindowLongW(my_hwnd, GWL_STYLE)
                user32.SetWindowLongW(my_hwnd, GWL_STYLE, style | WS_POPUP)
            else:
                user32.SetParent(my_hwnd, parent_hwnd)
        except Exception as e:
            Logger.error("WindowService", f"Parent attach failed: {e}")

    def _is_client_window(self, h) -> bool:
        if not user32: return False
        try:
            import psutil
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value == 0:
                return False
            proc = psutil.Process(pid.value)
            return proc.name().lower() in _CLIENT_PROCS
        except Exception:
            return False

    def _find_client_hwnd(self) -> int:
        if not user32: return 0
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
                        if self._is_client_window(h):
                            target_hwnd[0] = h
                            return False
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
            return target_hwnd[0]
        except Exception:
            return 0

    def _is_game_running(self) -> bool:
        from utils.client_detector import is_game_running
        return is_game_running()

    def _window_loop(self):
        last_hwnd = 0
        last_geom = (0, 0, 0, 0)
        last_topmost = None
        
        while self._running:
            try:
                if not user32:
                    time.sleep(1.0)
                    continue

                if not self._docked_mode:
                    # Undocked Mode: Ensure all registered windows are detached from parent
                    with self._lock:
                        for hwnd, info in self._registered_windows.items():
                            if info.get("attached", False):
                                self._attach_window(hwnd, 0)
                                info["attached"] = False
                    time.sleep(0.5)
                    continue

                hwnd = 0
                if last_hwnd != 0 and user32.IsWindow(last_hwnd) and self._is_client_window(last_hwnd):
                    hwnd = last_hwnd
                else:
                    hwnd = self._find_client_hwnd()

                if hwnd != 0:
                    if hwnd != last_hwnd or not self._is_dock_attached:
                        last_hwnd = hwnd
                        self._is_dock_attached = True
                        with self._lock:
                            for h, info in self._registered_windows.items():
                                self._attach_window(h, hwnd)
                                info["attached"] = True

                    # Minimize / Restore Sync
                    is_game_active = self._is_game_running()
                    is_client_minimized = (user32.IsIconic(hwnd) != 0) or (user32.IsWindowVisible(hwnd) == 0)
                    
                    if is_game_active:
                        if self._is_minimized_by_sync:
                            with self._lock:
                                for h, info in self._registered_windows.items():
                                    info["state_cb"]("restore")
                            self._is_minimized_by_sync = False
                            
                        # Game is active: do not set topmost
                        if last_topmost is not False:
                            with self._lock:
                                for h, info in self._registered_windows.items():
                                    info["state_cb"]("topmost_off")
                            last_topmost = False
                            
                    elif is_client_minimized:
                        if not self._is_minimized_by_sync:
                            with self._lock:
                                for h, info in self._registered_windows.items():
                                    info["state_cb"]("minimize")
                            self._is_minimized_by_sync = True
                    else:
                        if self._is_minimized_by_sync:
                            with self._lock:
                                for h, info in self._registered_windows.items():
                                    info["state_cb"]("restore")
                            self._is_minimized_by_sync = False

                        # Do Repositioning
                        rect = ctypes.wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        client_x = rect.left
                        client_y = rect.top
                        client_w = rect.right - rect.left
                        client_h = rect.bottom - rect.top
                        
                        if client_w > 100:
                            # Width of docked panel (defaults to 300, matches registered window width dynamically)
                            my_w = 300
                            with self._lock:
                                for h in self._registered_windows.keys():
                                    rect_reg = ctypes.wintypes.RECT()
                                    if user32.GetWindowRect(h, ctypes.byref(rect_reg)):
                                        my_w = rect_reg.right - rect_reg.left
                                        break
                            my_h = client_h
                            target_x = client_x + client_w
                            target_y = client_y
                            
                            # Clamp screen positioning
                            screen_w = user32.GetSystemMetrics(0) # SM_CXSCREEN
                            if target_x + my_w > screen_w:
                                target_x = client_x - my_w
                                
                            curr_geom = (target_x, target_y, my_w, my_h)
                            # Only update if geometry changed significantly (threshold = 2px)
                            if any(abs(curr_geom[i] - last_geom[i]) > 2 for i in range(4)):
                                with self._lock:
                                    for h, info in self._registered_windows.items():
                                        info["geom_cb"](target_x, target_y, my_w, my_h)
                                last_geom = curr_geom

                            # Dynamic Topmost Logic
                            fg_hwnd = user32.GetForegroundWindow()
                            is_active = (fg_hwnd == hwnd)
                            with self._lock:
                                for h in self._registered_windows:
                                    if fg_hwnd == h:
                                        is_active = True
                                        break
                                        
                            if is_active != last_topmost:
                                last_topmost = is_active
                                with self._lock:
                                    for h, info in self._registered_windows.items():
                                        info["state_cb"]("topmost_on" if is_active else "topmost_off")

                    time.sleep(0.05) # Docking poll interval
                else:
                    if self._is_dock_attached:
                        with self._lock:
                            for h, info in self._registered_windows.items():
                                self._attach_window(h, 0)
                                info["attached"] = False
                        self._is_dock_attached = False
                    last_hwnd = 0
                    last_geom = (0, 0, 0, 0)
                    last_topmost = None
                    time.sleep(0.5) # Docking idle interval
            except Exception as e:
                Logger.error("WindowService", f"Loop exception: {e}")
                time.sleep(0.1)

# Global singleton
_instance = None

def get_window_service(settings_service=None) -> WindowService:
    global _instance
    if _instance is None:
        _instance = WindowService(settings_service)
    return _instance
