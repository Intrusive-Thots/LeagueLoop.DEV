"""
Entry point for LeagueLoop application.
Restored and wired to ApplicationContainer.
"""
import ctypes
import os
import sys

_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

import threading
import time
import traceback
import queue
import subprocess
import tkinter as tk
from tkinter import TclError

import customtkinter as ctk  # type: ignore
import keyboard  # type: ignore
from PIL import Image  # type: ignore

from typing import Optional, TYPE_CHECKING

from core.container import ApplicationContainer  # type: ignore
from services.automation import AutomationEngine  # type: ignore
from utils.logger import Logger  # type: ignore
from utils.path_utils import get_asset_path  # type: ignore
from services.local_api import start_api_server  # type: ignore
from core.constants import (  # type: ignore
    SIDEBAR_WIDTH, SIDEBAR_HEIGHT, DOCKING_POLL_INTERVAL, DOCKING_IDLE_INTERVAL,
    CONNECTION_POLL_INTERVAL, CONNECTION_ERROR_INTERVAL,
    GEOMETRY_THRESHOLD,
)

from ui.app_sidebar import SidebarWidget  # type: ignore
from ui.components.factory import get_color, get_font  # type: ignore
from ui.components.toast import ToastManager  # type: ignore
from ui.components.mini_player import MiniPlayer
from ui.components.tray_icon import SystemTrayApp
from utils.focus_states import apply_focus_states_recursive
from tkinterdnd2 import TkinterDnD  # type: ignore

_SET_WINDOW_LONG = None
if hasattr(ctypes, "windll"):
    _SET_WINDOW_LONG = getattr(ctypes.windll.user32, "SetWindowLongPtrW", getattr(ctypes.windll.user32, "SetWindowLongW", None))

if TYPE_CHECKING:
    import ctypes.wintypes

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


def global_exception_handler(exc_type, exc_value, exp_traceback):
    """Global exception handler."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exp_value, exp_traceback)
        return
    err_str = "".join(traceback.format_exception(exc_type, exp_value, exp_traceback))
    Logger.error("SYS", f"Uncaught exception:\n{err_str}")


sys.excepthook = global_exception_handler


class LeagueLoopApp(ctk.CTk, TkinterDnD.DnDWrapper):
    """Main application window and controller for LeagueLoop."""
    def __init__(self):
        """Initializes the LeagueLoopApp via ApplicationContainer."""
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.report_callback_exception = self._on_tk_error
        
        self._ui_queue = queue.Queue()
        self._process_ui_queue()

        try:
            myappid = "league.loop.app.v1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
            
        self.title("LeagueLoop")
        try:
            icon_path = get_asset_path("assets/app.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
            else:
                backup = get_asset_path("assets/icon.png")
                self.iconphoto(False, tk.PhotoImage(file=backup))
        except Exception as e:
            Logger.warning("SYS", f"Could not set window icon: {e}")
        self.geometry(f"{SIDEBAR_WIDTH}x{SIDEBAR_HEIGHT}+100+100")
        self.minsize(260, 520)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        self.configure(fg_color=get_color("colors.background.app"))

        from utils.acrylic_blur import remove_blur
        self.after(100, lambda: remove_blur(self))

        try:
            ToastManager.get_instance(self)
        except Exception as e:
            Logger.error("SYS", f"ToastManager initialization error: {e}")
            
        # ApplicationContainer owns service construction
        self.container = ApplicationContainer()
        self.config = self.container.config
        self.assets = self.container.assets
        self.lcu = self.container.lcu
        self.scraper = self.container.scraper
        from core.state import State
        State.assets = self.assets
        
        self.running = True
        self._manually_hidden = False
        self._stop_event = threading.Event()
        self._drag_data = {"x": 0, "y": 0}

        self.stop_func = lambda: self.after(0, lambda: self.sidebar._on_power_click()) if hasattr(self, "sidebar") else None
        
        def _window_func(state):
            self.after(0, lambda: self._handle_window_state(state))
            
        def _queue_func(phase, state):
            if hasattr(self, "sidebar"):
                self.after(0, lambda: self.sidebar.update_queue_state(phase, state))
            if hasattr(self, "mini_player"):
                self.after(0, lambda: self.mini_player.update_state(phase))

        self.automation: Optional[AutomationEngine] = self.container.create_automation(
            log_func=None,
            stop_func=self.stop_func,
            stats_func=lambda team, bench, me=None: self.after(0, lambda: self.sidebar.update_lobby_stats(team, bench, me)) if hasattr(self, "sidebar") else None,
            window_func=_window_func,
            queue_func=_queue_func
        )

        self.setup_ui()
        
        auto = self.automation
        if auto is not None and hasattr(self, "sidebar"):
            auto.log = self.sidebar.update_action_log

        self.account_manager = self.container.create_account_manager(
            launch_client_func=self._hotkey_launch_client
        )
        if hasattr(self, "sidebar"):
            self.sidebar.set_account_manager(self.account_manager)

        self._setup_window_dragging()
        self.after(500, lambda: apply_focus_states_recursive(self.sidebar))

        self._launch_hotkey = None
        self._automation_hotkey = None
        self._queue_hotkey = None
        self._bind_hotkeys()

        if self.automation is not None:
            self.automation.start(start_paused=False)  # type: ignore

        self.assets.start_loading()
        
        self.tray = SystemTrayApp(self)
        if self.config.get("run_in_tray", True):
            self.tray.start()
            
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)

        self._local_ip, self._local_port = start_api_server(self, port=8337, bind_local=True)

        threading.Thread(target=self.connection_loop, daemon=True).start()
        threading.Thread(target=self.docking_loop, daemon=True).start()
        
        self.after(2000, self._auto_load_default_account)

    def _on_tk_error(self, *args):
        err = traceback.format_exception(*args) if len(args) == 3 else [str(args)]
        Logger.error("TK", "".join(err))

    def _process_ui_queue(self):
        try:
            while True:
                cb = self._ui_queue.get_nowait()
                try:
                    cb()
                except Exception as e:
                    Logger.debug("UI", f"queue cb: {e}")
        except queue.Empty:
            pass
        if self.running:
            self.after(50, self._process_ui_queue)

    def setup_ui(self):
        self.sidebar = SidebarWidget(self, self.toggle_power, self.config, lcu=self.lcu, assets=self.assets, scraper=self.scraper)
        self.sidebar.pack(fill="both", expand=True)
        self.mini_player = MiniPlayer(self, self.config)

    def toggle_power(self, state):
        if self.automation is not None:
            if state:
                self.automation.resume()
            else:
                self.automation.pause()

    def _auto_load_default_account(self):
        if not self.lcu.is_connected:
            default_idx = self.account_manager.get_default_account_index()
            if default_idx >= 0:
                Logger.info("SYS", "Auto-loading default account...")
                if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                    self.sidebar.update_action_log("Auto-loading default account...")
                if not self.account_manager.riot_client.is_riot_client_running():
                    self._hotkey_launch_client()
                self.after(3000, lambda: self.account_manager.login_account(
                    default_idx,
                    log_func=self.sidebar.update_action_log if hasattr(self, "sidebar") else None
                ))

    def _on_close_request(self):
        if self.config.get("run_in_tray", True):
            self._manually_hidden = True
            self.withdraw()
        else:
            self._on_close()

    def _on_close(self):
        Logger.info("SYS", "Exit requested — shutting down...")
        self.running = False
        self._stop_event.set()
        try:
            if hasattr(self, "container") and self.container:
                self.container.shutdown()
            elif hasattr(self, "automation") and self.automation:
                self.automation.stop()
        except Exception as e:
            Logger.debug("SYS", f"Engine stop error: {e}")
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        Logger.info("SYS", "Shutdown complete.")
        os._exit(0)

    def _setup_window_dragging(self):
        pass

    def _bind_hotkeys(self):
        pass

    def _hotkey_launch_client(self):
        pass

    def connection_loop(self):
        while self.running:
            time.sleep(CONNECTION_POLL_INTERVAL)

    def docking_loop(self):
        while self.running:
            time.sleep(DOCKING_POLL_INTERVAL)

    def _handle_window_state(self, state):
        pass

    def on_settings_saved(self):
        pass

    def on_dock_toggled(self, docked):
        pass

    def _show_mobile_qr(self):
        pass


def _kill_other_instances():
    """Terminate any other running instances of LeagueLoop."""
    try:
        import psutil  # type: ignore
        my_pid = os.getpid()
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["pid"] == my_pid:
                    continue
                cmdline = proc.info.get("cmdline") or []
                if any("LeagueLoop" in str(c) or "run.py" in str(c) for c in cmdline):
                    if proc.info["name"] and "python" in proc.info["name"].lower():
                        proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass
