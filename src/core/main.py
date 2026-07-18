"""
Entry point for LeagueLoop application.
"""
import ctypes
import os
import sys

# Ensure 'src' is in the Python path when executed directly
_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

import threading
import time
import traceback
import queue
import tkinter as tk
from tkinter import TclError

import customtkinter as ctk  # type: ignore
import keyboard  # type: ignore
from PIL import Image  # type: ignore

from typing import Optional, TYPE_CHECKING

from services.api_handler import LCUClient  # type: ignore
from services.asset_manager import AssetManager, ConfigManager  # type: ignore
from services.automation import AutomationEngine  # type: ignore
from services.account_manager import get_account_manager  # type: ignore
from services.stats_scraper import StatsScraper  # type: ignore
from services.settings_service import get_settings_service
from services.league_service import get_league_service
from services.friend_service import get_friend_service
from services.champion_service import get_champion_service
from services.draft_service import get_draft_service
from services.window_service import get_window_service
from services.notification_service import get_notification_service
from services.queue_service import get_queue_service
from utils.logger import Logger  # type: ignore
from utils.path_utils import get_asset_path  # type: ignore
from core.version import __version__  # type: ignore
from core.events import EventBus
from services.api import start_api_server # type: ignore
from core.constants import (  # type: ignore
    SIDEBAR_WIDTH, SIDEBAR_HEIGHT,
    CONNECTION_POLL_INTERVAL, CONNECTION_ERROR_INTERVAL,
)

from ui.sidebar.sidebar import SidebarWidget  # type: ignore
from ui.components.factory import get_color, get_font, TOKENS  # type: ignore
from ui.components.toast import ToastManager  # type: ignore
from ui.ui_shared import CTkTooltip  # type: ignore
from ui.components.mini_player import MiniPlayer
from ui.components.tray_icon import SystemTrayApp
from utils.acrylic_blur import apply_acrylic_blur
from utils.focus_states import apply_focus_states_recursive
from tkinterdnd2 import TkinterDnD  # type: ignore

from core.window_manager import WindowManagerMixin
from core.hotkey_manager import HotkeyManagerMixin

if TYPE_CHECKING:
    import ctypes.wintypes

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Global exception handler."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    err_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    Logger.error("SYS", f"Uncaught exception:\n{err_str}")

sys.excepthook = global_exception_handler

class LeagueLoopApp(WindowManagerMixin, HotkeyManagerMixin, ctk.CTk, TkinterDnD.DnDWrapper):
    """Main application window and controller for LeagueLoop."""
    def __init__(self):
        """Initializes the LeagueLoopApp."""
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
            
        self.title("League Loop")
        try:
            icon_path = get_asset_path("assets/app.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
            else:
                backup = get_asset_path("assets/icon.png")
                self.iconphoto(False, tk.PhotoImage(file=backup))
        except Exception as e:
            Logger.warning("SYS", f"Could not set window icon: {e}")
        self.geometry(f"{SIDEBAR_WIDTH}x{SIDEBAR_HEIGHT}+100+100") # Spawn visibly on screen
        self.minsize(260, 520)
        self.overrideredirect(True) # Borderless for docking
        self.attributes("-topmost", True) # Keep visible until docked
        
        self.configure(fg_color=get_color("colors.background.app"))

        # NOTE: Acrylic blur disabled — Win32 SetWindowCompositionAttribute makes
        # the entire CTk window translucent/unreadable. Actively remove any
        # residual blur from prior sessions.
        from utils.acrylic_blur import remove_blur
        self.after(100, lambda: remove_blur(self))

        try:
            ToastManager.get_instance(self)
        except Exception as e:
            Logger.error("SYS", f"ToastManager initialization error: {e}")
            
        self.config = ConfigManager()
        self.assets = AssetManager()
        from core.state import State
        State.assets = self.assets
        self.lcu = LCUClient()
        self.scraper = StatsScraper(mode=self.config.get("aram_mode", "ARAM"))
        
        # Initialize Service Layer Singletons
        self.settings_service = get_settings_service(self.config)
        self.league_service = get_league_service(self.lcu)
        self.friend_service = get_friend_service(self.settings_service, self.league_service)
        self.champion_service = get_champion_service(self.assets, self.scraper)
        self.draft_service = get_draft_service(self.league_service)
        self.window_service = get_window_service(self.settings_service)
        self.notification_service = get_notification_service()
        self.queue_service = get_queue_service(self.settings_service, self.league_service)
        self.window_service.start()
        
        self.running = True
        self._manually_hidden = False
        self._stop_event = threading.Event()
        self._drag_data = {"x": 0, "y": 0}

        # Initialize automation before UI to avoid NoneType in callbacks
        self.stop_func = lambda: self.after(0, lambda: self.sidebar._on_power_click()) if hasattr(self, "sidebar") else None

        # Subscribe to EventBus events from AutomationEngine (thread-safe via self.after)
        EventBus.on("automation_window_state", lambda state: self.after(0, lambda: self._handle_window_state(state)))
        EventBus.on("automation_queue_state", lambda phase, state: (
            self.after(0, lambda: self.sidebar.update_queue_state(phase, state)) if hasattr(self, "sidebar") else None,
            self.after(0, lambda: self.mini_player.update_state(phase)) if hasattr(self, "mini_player") else None
        ))
        EventBus.on("automation_lobby_stats", lambda team, bench, me=None: (
            self.after(0, lambda: self.sidebar.update_lobby_stats(team, bench, me)) if hasattr(self, "sidebar") else None
        ))
        
        # Subscribe to Remote API/Action Events
        EventBus.on("action:find_match", lambda: self.after(0, self._hotkey_find_match))
        EventBus.on("action:launch_client", lambda: self.after(0, self._hotkey_launch_client))
        EventBus.on("action:toggle_automation", lambda: self.after(0, self._hotkey_toggle_automation))
        EventBus.on("action:set_status", lambda msg: threading.Thread(target=lambda: self.automation.set_custom_status(msg), daemon=True).start() if self.automation else None)
        EventBus.on("action:mass_invite", lambda: threading.Thread(target=lambda: self.automation.mass_invite_friends(), daemon=True).start() if self.automation else None)

        self.automation: Optional[AutomationEngine] = AutomationEngine(
            self.lcu,
            self.assets,
            self.config,
            log_func=None,
            stop_func=self.stop_func,
        )

        self.setup_ui()
        
        # Link automation to sidebar log
        auto = self.automation
        if auto is not None and hasattr(self, "sidebar"):
            auto.log = self.sidebar.update_action_log

        # Initialize account manager and inject into sidebar
        self.account_manager = get_account_manager(
            lcu=self.lcu,
            launch_client_func=self._hotkey_launch_client
        )
        if hasattr(self, "sidebar"):
            self.sidebar.set_account_manager(self.account_manager)

        self._setup_window_dragging()

        # Apply keyboard focus rings to all interactive elements (deferred to ensure all children exist)
        self.after(500, lambda: apply_focus_states_recursive(self.sidebar))

        # Keyboard shortcuts
        self._launch_hotkey = None
        self._automation_hotkey = None
        self._queue_hotkey = None
        self._bind_hotkeys()

        if self.automation is not None:
            self.automation.start(start_paused=False)  # type: ignore

        self.assets.start_loading()
        
        # Tray Icon Initialization
        self.tray = SystemTrayApp(self)
        if self.config.get("run_in_tray", True):
            self.tray.start()
            
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)

        # Start background API server
        self._local_ip, self._local_port = start_api_server(self, port=8337)

        threading.Thread(target=self.connection_loop, daemon=True).start()
        
        # Register CustomTkinter window with WindowService
        self.window_service.register_window(
            self.winfo_id(),
            lambda x, y, w, h: self.after(0, lambda: self.geometry(f"{w}x{h}+{x}+{y}")),
            self._handle_window_service_state
        )
        
        # Auto-load default account on startup
        self.after(2000, self._auto_load_default_account)
        
    def _auto_load_default_account(self):
        """Auto-load default account if client is not connected on startup."""
        if not self.lcu.is_connected:
            default_idx = self.account_manager.get_default_account_index()
            if default_idx >= 0:
                Logger.info("SYS", "Auto-loading default account...")
                if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                    self.sidebar.update_action_log("Auto-loading default account...")
                
                # Check if Riot Client is already running; if not, launch it first!
                if not self.account_manager.riot_client.is_riot_client_running():
                    self._hotkey_launch_client()
                    
                # Schedule login_account after a brief pause to let client launch
                self.after(3000, lambda: self.account_manager.login_account(
                    default_idx,
                    log_func=self.sidebar.update_action_log if hasattr(self, "sidebar") else None
                ))

    def _on_tk_error(self, exc, val, tb):
        """Log Tkinter callback errors."""
        err_str = "".join(traceback.format_exception(exc, val, tb))
        Logger.error("UI", f"Tkinter Error:\n{err_str}")

    def _process_ui_queue(self):
        """Processes the thread-safe UI task queue to execute background tasks on the main thread."""
        for _ in range(100):
            if self._ui_queue.empty():
                break
            try:
                task, args, kwargs = self._ui_queue.get_nowait()
                if task:
                    try:
                        task(*args, **kwargs)
                    except Exception as e:
                        if "isn't packed" not in str(e):
                            Logger.error("UI_QUEUE", f"Error in UI task: {e}")
            except queue.Empty:
                pass
        super().after(16, self._process_ui_queue)

    def after(self, ms, func=None, *args):
        """Overrides after to handle exceptions."""
        if threading.current_thread() is threading.main_thread():
            return super().after(ms, func, *args)
        else:
            if ms == 0:
                self._ui_queue.put((func, args, {}))
            else:
                self._ui_queue.put((super().after, (ms, func) + args, {}))
            return "queued"

    def setup_ui(self):
        """Sets up the user interface."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.sidebar = SidebarWidget(self, self.toggle_power, self.config, lcu=self.lcu, assets=self.assets, scraper=self.scraper)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.mini_player = MiniPlayer(self, self.config)

    def on_settings_saved(self):
        """Handles settings saved event."""
        self._bind_hotkeys()
        self.scraper.set_mode(self.config.get("aram_mode", "ARAM"))

    def toggle_power(self, power_state):
        """Toggles the automation power."""
        Logger.info("SYS", f"Power Toggled: {power_state}")
        if self.automation is not None:
            if power_state:
                self.automation.resume()  # type: ignore
            else:
                self.automation.pause()  # type: ignore

    def connection_loop(self):
        """Background loop to maintain connection."""
        last_state = None
        while self.running and not self._stop_event.is_set():
            try:
                current_state = self.lcu.is_connected
                if current_state != last_state:
                    last_state = current_state
                    if hasattr(self, "sidebar") and hasattr(self.sidebar, "on_lcu_connection_changed"):
                        self.after(0, lambda s=current_state: getattr(self, "sidebar").on_lcu_connection_changed(s))

                if not current_state:
                    connected = self.lcu.connect()
                    if connected:
                        Logger.info("LCU", "Connected to League Client")
                        self.after(0, lambda: self.sidebar.lbl_action.configure(text="Connected!"))
                    else:
                        self.after(0, lambda: self.sidebar.lbl_action.configure(text="Waiting for Client..."))
                time.sleep(CONNECTION_POLL_INTERVAL)
            except Exception as e:
                Logger.error("SYS", f"Connection loop error: {e}")
                time.sleep(CONNECTION_ERROR_INTERVAL)

    def _on_close(self):
        """Robust shutdown: stop all subsystems, then force-exit."""
        Logger.info("SYS", "Exit requested — shutting down...")
        self.running = False
        self._stop_event.set()

        # 1. Stop the automation engine
        try:
            if hasattr(self, 'automation') and self.automation:
                self.automation.stop()
        except Exception as e:
            Logger.debug("SYS", f"Engine stop error: {e}")

        # 1.5 Stop WindowService
        try:
            if hasattr(self, 'window_service') and self.window_service:
                self.window_service.unregister_window(self.winfo_id())
                self.window_service.stop()
        except Exception as e:
            Logger.debug("SYS", f"WindowService stop error: {e}")

        # 2. Unhook keyboard hotkeys
        try:
            keyboard.unhook_all()
        except Exception as e:
            Logger.debug("SYS", f"Unhook error: {e}")

        # 3. Destroy the Tk window
        try:
            self.destroy()
        except Exception as e:
            Logger.debug("SYS", f"Destroy error: {e}")

        # 4. Force-exit to kill any lingering daemon threads
        Logger.info("SYS", "Shutdown complete.")
        os._exit(0)

def _kill_other_instances():
    """Terminate any other running instances of LeagueLoop."""
    import psutil  # type: ignore
    my_pid = os.getpid()
    # Also protect the parent (e.g. the shell that launched us)
    try:
        my_parent_pid = psutil.Process(my_pid).ppid()
    except Exception:
        my_parent_pid = -1
    
    safe_pids = {my_pid, my_parent_pid}
    killed = 0
    
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.pid in safe_pids:
                continue
            pname = (proc.info.get("name") or "").lower()
            is_leagueloop_exe = "leagueloop" in pname
            is_python_script = "python" in pname

            if not (is_leagueloop_exe or is_python_script):
                continue
                
            if is_python_script:
                try:
                    cmdline = proc.cmdline()
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                cmdline_str = " ".join(cmdline).lower()
                if "core.main" not in cmdline_str and "core\\main" not in cmdline_str and "run.py" not in cmdline_str:
                    continue
            
            # Reachable if it's LeagueLoop.exe OR the python core.main script
            Logger.info("SYS", f"Killing stale instance PID {proc.pid} ({pname})")
            proc.kill()
            killed += 1  # type: ignore
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    if killed:
        Logger.info("SYS", f"Terminated {killed} stale instance(s).")
        time.sleep(0.3)

if __name__ == "__main__":
    _kill_other_instances()
    app = LeagueLoopApp()
    app.mainloop()
