"""
Entry point for LeagueLoop application.
"""
import ctypes
import os
import random
import sys

# Ensure 'src' is in the Python path when executed directly
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

from services.api_handler import LCUClient  # type: ignore
from services.asset_manager import AssetManager, ConfigManager  # type: ignore
from services.automation import AutomationEngine  # type: ignore
from services.account_manager import AccountManager  # type: ignore
from services.stats_scraper import StatsScraper  # type: ignore
from services.settings_service import get_settings_service
from services.league_service import get_league_service
from services.friend_service import get_friend_service
from services.champion_service import get_champion_service
from services.draft_service import get_draft_service
from services.window_service import get_window_service
from services.notification_service import get_notification_service
from utils.logger import Logger  # type: ignore
from utils.path_utils import get_asset_path  # type: ignore
from core.version import __version__  # type: ignore
from core.events import EventBus
from services.local_api import start_api_server # type: ignore
from core.constants import (  # type: ignore
    SIDEBAR_WIDTH, SIDEBAR_HEIGHT, DOCKING_POLL_INTERVAL, DOCKING_IDLE_INTERVAL,
    CONNECTION_POLL_INTERVAL, CONNECTION_ERROR_INTERVAL,
    GEOMETRY_THRESHOLD,
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

_SET_WINDOW_LONG = None
if hasattr(ctypes, "windll"):
    _SET_WINDOW_LONG = getattr(ctypes.windll.user32, "SetWindowLongPtrW", getattr(ctypes.windll.user32, "SetWindowLongW", None))

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

class LeagueLoopApp(ctk.CTk, TkinterDnD.DnDWrapper):
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
        self.account_manager = AccountManager(
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
            self.withdraw()  # hide the window
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

    def _on_tk_error(self, exc, val, tb):
        """Log Tkinter callback errors."""
        err_str = "".join(traceback.format_exception(exc, val, tb))
        Logger.error("UI", f"Tkinter Error:\n{err_str}")

    def _process_ui_queue(self):
        """Processes the thread-safe UI task queue to execute background tasks on the main thread."""
        # Bolt optimization: checking .empty() is faster than catching queue.Empty
        # in a 16ms polling loop where the queue is usually empty.
        for _ in range(100):
            if self._ui_queue.empty():
                break
            try:
                task, args, kwargs = self._ui_queue.get_nowait()
                if task:
                    try:
                        task(*args, **kwargs)
                    except Exception as e:
                        # Suppress benign TclError from pack_forget'd widgets
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

    def _hotkey_find_match(self):
        """Invokes the match finder via global hotkey registration."""
        self.state("normal")
        self.attributes("-topmost", True)
        self.after(0, self.sidebar._find_match)

    def _handle_window_state(self, state):
        if state == "minimize":
            self.attributes("-topmost", False)
            try:
                import ctypes
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
                import ctypes
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
            # Stealth Mode: restore the window without stealing focus or lifting.
            # The window becomes visible again but stays behind the active window,
            # so it doesn't flash on screen for streamers or observers.
            try:
                import ctypes
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
            import ctypes
            GWLP_HWNDPARENT = -8
            my_hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if my_hwnd == 0:
                my_hwnd = self.winfo_id()
                
            # For 64-bit windows, SetWindowLongPtr is required.
            if _SET_WINDOW_LONG:
                _SET_WINDOW_LONG(my_hwnd, GWLP_HWNDPARENT, parent_hwnd)
                
        except Exception:
            pass

    def _hotkey_launch_client(self):
        def _launch():
            path_override = self.config.get("league_path_override", "")
            if path_override and os.path.exists(path_override):
                candidates = [path_override]
            else:
                candidates = []
                try:
                    from utils.client_detector import resolve_installation_paths
                    _, rc_install_dir = resolve_installation_paths()
                    if rc_install_dir:
                        rc_path = os.path.join(rc_install_dir, "RiotClientServices.exe")
                        if os.path.exists(rc_path):
                            candidates.append(rc_path)
                except Exception as e:
                    Logger.debug("SYS", f"Failed resolving installs: {e}")
                
                candidates.extend([
                    r"C:\Riot Games\Riot Client\RiotClientServices.exe",
                    r"D:\Riot Games\Riot Client\RiotClientServices.exe",
                    r"E:\Riot Games\Riot Client\RiotClientServices.exe",
                    r"C:\Program Files (x86)\Riot Games\Riot Client\RiotClientServices.exe",
                    os.path.join(os.environ.get("USERPROFILE", ""), r"Riot Games\Riot Client\RiotClientServices.exe")
                ])
                
                # Proactive Registry Lookup
                try:
                    import winreg
                    for hkey in [getattr(winreg, "HKEY_CURRENT_USER", 0), getattr(winreg, "HKEY_LOCAL_MACHINE", 0)]:
                        try:
                            key = getattr(winreg, "OpenKey")(hkey, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game league_of_legends.live")
                            val, _ = getattr(winreg, "QueryValueEx")(key, "UninstallString")
                            # Typically "C:\Riot Games\Riot Client\RiotClientServices.exe" --uninstall-product=...
                            if val and "RiotClientServices.exe" in val:
                                path = val.split('"')[1] if '"' in val else val.split(' ')[0]
                                if os.path.exists(path): candidates.insert(0, path)
                        except FileNotFoundError:
                            pass
                        except Exception as e:
                            from utils.logger import Logger  # type: ignore
                            Logger.debug("SYS", f"Registry iteration failed: {e}")
                except Exception as e:
                    from utils.logger import Logger  # type: ignore
                    Logger.debug("SYS", f"Registry module failed: {e}")

            for c in candidates:
                if os.path.exists(c):
                    if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                        self.sidebar.update_action_log("Launching Riot Client...")
                    args = "--launch-product=league_of_legends --launch-patchline=live"
                    try:
                        # Use ShellExecuteW to handle UAC elevation gracefully
                        ret = ctypes.windll.shell32.ShellExecuteW(
                            None, "open", c, args, None, 1  # SW_SHOWNORMAL
                        )
                        if ret <= 32:
                            # ShellExecute failed, fall back to subprocess
                            subprocess.Popen([c] + args.split(), creationflags=subprocess.CREATE_NO_WINDOW)
                    except Exception:
                        try:
                            subprocess.Popen([c] + args.split(), creationflags=subprocess.CREATE_NO_WINDOW)
                        except OSError:
                            # WinError 740: requires elevation — retry with runas
                            ctypes.windll.shell32.ShellExecuteW(
                                None, "runas", c, args, None, 1
                            )
                    return
            if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                self.sidebar.update_action_log("Error: Could not find Riot Client.")
        self.after(0, _launch)

    def _hotkey_toggle_automation(self):
        self.after(0, self.sidebar._on_power_click)


    def _switch_account_by_label(self, label):
        """Switch to an account identified by its label."""
        if not hasattr(self, "account_manager"):
            return
        for i, acct in enumerate(self.account_manager.get_accounts()):
            if acct.get("label", "") == label:
                def _log(msg):
                    if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                        self.sidebar.update_action_log(msg)
                self.account_manager.login_account(i, log_func=_log)
                return

    def _show_mobile_qr(self):
        """Shows a popup with the QR code and IP to connect the mobile app."""
        if not self._local_ip:
            ToastManager.get_instance().show("API Server not running.", theme="error")
            return
            
        popup = ctk.CTkToplevel(self)
        popup.title("Link Mobile Device")
        popup.geometry("300x350")
        popup.attributes("-topmost", True)
        popup.resizable(False, False)
        
        lbl_info = ctk.CTkLabel(popup, text=f"Connect your phone to:", font=get_font("fonts.body"))
        lbl_info.pack(pady=(20, 5))
        
        lbl_ip = ctk.CTkLabel(popup, text=f"{self._local_ip}:{self._local_port}", font=get_font("fonts.title"), text_color=get_color("colors.accent.primary"))
        lbl_ip.pack(pady=5)
        
        # We will attempt to fetch a QR code image from qrserver.com
        qr_url = f"http://api.qrserver.com/v1/create-qr-code/?data=http://{self._local_ip}:{self._local_port}&size=200x200"
        
        import threading
        import urllib.request
        from io import BytesIO
        from PIL import Image

        img_label = ctk.CTkLabel(popup, text="Loading QR Code...")
        img_label.pack(pady=10)

        def _fetch_qr():
            try:
                with urllib.request.urlopen(qr_url, timeout=5) as u:
                    raw_data = u.read()
                image = Image.open(BytesIO(raw_data))
                ctk_img = ctk.CTkImage(light_image=image, dark_image=image, size=(200, 200))
                self.after(0, lambda: img_label.configure(image=ctk_img, text=""))
            except Exception as e:
                self.after(0, lambda: img_label.configure(text=f"Failed to load QR.\nPlease connect manually via IP."))

        threading.Thread(target=_fetch_qr, daemon=True).start()

    def _quick_queue(self, mode_name):
        if not hasattr(self, "sidebar") or not self.sidebar.winfo_exists():
            return

        self.sidebar._on_mode_change(mode_name)
        self.after(50, self.sidebar._find_match)

        try:
            ToastManager.get_instance().show(
                f"Queued up for {mode_name}!",
                icon="🎮",
                duration=3000,
                theme="success"
            )
        except Exception as e:
            Logger.error("SYS", f"Toast error: {e}")

    def _queue_roulette(self):
        if not hasattr(self, "sidebar") or not self.sidebar.winfo_exists():
            return

        modes = [
            "Quickplay", "Draft Pick", "Ranked Solo/Duo", "Ranked Flex",
            "ARAM", "Arena", "Brawl", "TFT Normal"
        ]

        # 1. Cancel existing search
        if getattr(self.sidebar, "power_state", False):
            self.sidebar._on_power_click()

        # 2. Spin animation parameters
        spins = random.randint(15, 25)
        delay = 50
        
        # Track the last rolled mode in a mutable container
        state = {"current": "ARAM"}

        def do_spin(count):
            """Animates a spinner."""
            if count > 0:
                state["current"] = random.choice(modes)
                if hasattr(self.sidebar, "queue_label"):
                    self.sidebar.queue_label.configure(text=state["current"])

                # Slow down towards the end
                next_delay = delay + int((spins - count) * 4)
                self.after(next_delay, lambda: do_spin(count - 1))
            else:
                # Landed!
                winner = state["current"]
                self.sidebar._on_mode_change(winner)

                try:
                    ToastManager.get_instance().show(
                        f"Roulette landed on {winner}!",
                        icon="🎰",
                        duration=4000,
                        theme="success",
                        confetti=True
                    )
                except Exception as e:
                    Logger.error("SYS", f"Toast error: {e}")

                # Queue it up
                self.after(500, self.sidebar._find_match)

        # Start spin
        do_spin(spins)

    def _restart_ux(self):
        if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
            self.sidebar.update_action_log("Restarting League UX...")
        
        def _execute():
            success = False
            if self.lcu and self.lcu.is_connected:
                res = self.lcu.request("POST", "/riotclient/kill-and-restart-ux")
                if res and res.status_code in [200, 204]:
                    success = True
            
            if not success:
                import subprocess
                subprocess.run(["taskkill", "/IM", "LeagueClientUx.exe", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
            self.after(0, lambda: self.sidebar.update_action_log("UX Restart Triggered."))
                
        threading.Thread(target=_execute, daemon=True).start()

    def _bind_hotkeys(self):
        try:
            keyboard.unhook_all()
        except Exception as e:
            Logger.debug("SYS", f"Failed to unhook hotkeys: {e}")
            
        self._launch_hotkey = self.config.get("hotkey_launch_client", "ctrl+shift+l")
        self._automation_hotkey = self.config.get("hotkey_toggle_automation", "ctrl+shift+a")
        self._queue_hotkey = self.config.get("hotkey_find_match", "ctrl+shift+f")
        self._mini_hotkey = self.config.get("hotkey_compact_mode", "ctrl+shift+m")

        try:
            keyboard.add_hotkey(self._launch_hotkey, self._hotkey_launch_client, suppress=False)
            keyboard.add_hotkey(self._automation_hotkey, self._hotkey_toggle_automation, suppress=False)
            keyboard.add_hotkey(self._queue_hotkey, self._hotkey_find_match, suppress=False)
            keyboard.add_hotkey(self._mini_hotkey, lambda: self.after(0, self.mini_player.toggle), suppress=False)
        except Exception as e:
            Logger.error("SYS", f"Failed to register hotkeys: {e}")

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

    def docking_loop(self):
        """Finds League of Legends client and clips to the right side of it."""
        import psutil
        last_hwnd = 0
        last_geom = (0, 0, 0, 0) # x, y, w, h
        last_topmost = None
        self._is_dock_attached = False
        self._is_minimized_by_sync = False
        
        # All known process names for visible Riot/League windows
        _CLIENT_PROCS = {
            "leagueclientux.exe",      # Main League client UI
            "leagueclient.exe",        # League backend (sometimes owns a window)
            "riot client.exe",         # Riot Client launcher (note the space)
            "riotclientux.exe",        # Riot Client UI (older builds)
            "riotclientservices.exe",  # Riot Client services backend
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

        # All known window titles for Riot/League client windows
        _CLIENT_TITLES = {"league of legends", "riot client"}

        def find_client_hwnd():
            try:
                target_hwnd = [0]
                def enum_callback(h, extra):
                    if not user32.IsWindowVisible(h):
                        return True  # Skip invisible windows
                    length = user32.GetWindowTextLengthW(h)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(h, buf, length + 1)
                        title = buf.value.lower().strip()
                        if title in _CLIENT_TITLES:
                            if is_client_window(h):
                                target_hwnd[0] = h
                                return False  # Stop enumeration
                    return True
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
                user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
                return target_hwnd[0]
            except Exception:
                return 0

        def is_game_process_running():
            try:
                for p in psutil.process_iter(attrs=["name"]):
                    if p.info["name"] and p.info["name"].lower() == "league of legends.exe":
                        return True
            except Exception:
                pass
            return False

        while self.running and not self._stop_event.is_set():  # type: ignore
            try:
                hwnd = 0
                windll = getattr(ctypes, "windll", None)
                user32 = getattr(windll, "user32", None) if windll else None
                
                if not user32:
                    time.sleep(2.0)
                    continue

                # Sync state with League/Riot Client (no bypass during game)
                if last_hwnd != 0 and user32.IsWindow(last_hwnd) and is_client_window(last_hwnd):
                    hwnd = last_hwnd
                else:
                    hwnd = find_client_hwnd()

                if hwnd != 0:
                    if hwnd != last_hwnd or not self._is_dock_attached:
                        last_hwnd = hwnd
                        self.after(0, lambda h=hwnd: self._attach_to_hwnd(h))
                        self._is_dock_attached = True

                    # Mirror client window state: minimize if client is minimized or invisible
                    # EXCEPT when the game is active.
                    is_game_active = is_game_process_running()
                    is_client_minimized = (user32.IsIconic(hwnd) != 0) or (user32.IsWindowVisible(hwnd) == 0)
                    
                    if is_game_active:
                        # Game is active: do not minimize, and restore if minimized by sync
                        if self._is_minimized_by_sync and not self._manually_hidden:
                            self.after(0, lambda: self._handle_window_state("restore"))
                            self._is_minimized_by_sync = False
                        
                        # Ensure topmost is False so we don't cover the game window
                        if last_topmost is not False:
                            self.after(0, lambda: self.attributes("-topmost", False))
                            last_topmost = False
                    elif is_client_minimized:
                        # Client minimized/invisible -> minimize LeagueLoop
                        if self.state() != "withdrawn" and self.state() != "iconic" and not self._is_minimized_by_sync:
                            self.after(0, lambda: self._handle_window_state("minimize"))
                            self._is_minimized_by_sync = True
                    else:
                        # Client restored/visible -> restore LeagueLoop if minimized by sync and not manually hidden
                        if self._is_minimized_by_sync and not self._manually_hidden:
                            self.after(0, lambda: self._handle_window_state("restore"))
                            self._is_minimized_by_sync = False

                        # Do docking/repositioning
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
                            
                            # Clamp target_x so application doesn't get pushed off-screen if client is on the edge
                            screen_w = self.winfo_screenwidth()
                            if target_x + my_w > screen_w:
                                target_x = client_x - my_w
                            
                            curr_geom = (target_x, target_y, my_w, my_h)
                            if any(abs(curr_geom[i] - last_geom[i]) > GEOMETRY_THRESHOLD for i in range(4)):  # type: ignore
                                self.after(0, lambda x=target_x, y=target_y, h=my_h: self.geometry(f"{my_w}x{h}+{x}+{y}"))
                                last_geom = curr_geom
                                
                            # DYNAMIC TOPMOST LOGIC
                            fg_hwnd = user32.GetForegroundWindow()
                            my_id = user32.GetParent(self.winfo_id())
                            if my_id == 0: 
                                my_id = self.winfo_id()
                                
                            # Topmost & Visible only if Riot Client, or League Client, or LeagueLoop is active
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
                    # Client not running / closed: detach and clean up
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
