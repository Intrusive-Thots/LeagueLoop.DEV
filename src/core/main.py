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
from utils.client_detector import get_riot_executable_path, get_league_executable_path
from tkinterdnd2 import TkinterDnD  # type: ignore

_SET_WINDOW_LONG = None
if hasattr(ctypes, "windll"):
    _SET_WINDOW_LONG = getattr(ctypes.windll.user32, "SetWindowLongPtrW", getattr(ctypes.windll.user32, "SetWindowLongW", None))

if TYPE_CHECKING:
    import ctypes.wintypes

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


def global_exception_handler(exc_type, exp_value, exp_traceback):
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
        
        self.running = True
        self._manually_hidden = False
        self._stop_event = threading.Event()
        self._drag_data = {"x": 0, "y": 0}
        self._ui_queue = queue.Queue()
        self._process_ui_queue()

        try:
            myappid = "league.loop.app.v1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as exc:
            Logger.debug("Main", "__init__ suppressed an error", exc=exc)
            
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

        self.stop_func = lambda: self.after(0, lambda: self.sidebar._on_power_click()) if hasattr(self, "sidebar") else None
        
        def _window_func(state):
            self.after(0, lambda: self._handle_window_state(state))
            
        def _queue_func(phase, state):
            if hasattr(self, "sidebar"):
                self.after(0, lambda: self.sidebar.update_queue_state(phase, state))
            if hasattr(self, "mini_player"):
                self.after(0, lambda: self.mini_player.update_state(phase))

        # Shared startup sequence (assets, automation, accounts, client
        # state). The Qt shell calls the same method, so a service added to
        # `bootstrap()` reaches both shells instead of only whichever one the
        # author happened to be editing.
        self.container.bootstrap(
            launch_client_func=self._hotkey_launch_client,
            automation_hooks=dict(
                log_func=None,
                stop_func=self.stop_func,
                stats_func=lambda team, bench, me=None: self.after(
                    0, lambda: self.sidebar.update_lobby_stats(team, bench, me)
                ) if hasattr(self, "sidebar") else None,
                window_func=_window_func,
                queue_func=_queue_func,
            ),
            start_assets=False,   # started below, after the UI can show progress
        )
        self.automation: Optional[AutomationEngine] = self.container.automation
        
        self.setup_ui()
        
        auto = self.automation
        if auto is not None and hasattr(self, "sidebar"):
            auto.log = self.sidebar.update_action_log

        # Already built by bootstrap(); just take the reference.
        self.account_manager = self.container.account_manager
        if hasattr(self, "sidebar"):
            # The reason travels with the None. Without it the panel could
            # only say "unavailable", which tells the user nothing they can
            # act on.
            reason = ""
            if self.account_manager is None:
                getter = getattr(self.container, "failure_reason", None)
                if callable(getter):
                    reason = getter("accounts")
            self.sidebar.set_account_manager(self.account_manager, reason)

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
        if getattr(self, "running", False):
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
        # Scheduled with `after()` at startup, so it fires whatever happened
        # during bootstrap. With the account service down this raised
        # AttributeError inside a Tk callback — swallowed into the log, and
        # the user just saw auto-login silently never happen.
        if self.account_manager is None:
            Logger.info(
                "SYS",
                "Skipping auto-login: the account service is not available "
                "this run.",
            )
            return
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
        except Exception as exc:
            Logger.debug("Main", "_on_close suppressed an error", exc=exc)
        try:
            self.destroy()
        except Exception as exc:
            Logger.debug("Main", "_on_close suppressed an error", exc=exc)
        Logger.info("SYS", "Shutdown complete.")
        os._exit(0)

    def _setup_window_dragging(self):
        """Enable drag for borderless window via left mouse."""
        def start_drag(event):
            self._drag_data["x"] = event.x
            self._drag_data["y"] = event.y

        def do_drag(event):
            x = self.winfo_x() + (event.x - self._drag_data["x"])
            y = self.winfo_y() + (event.y - self._drag_data["y"])
            self.geometry(f"+{x}+{y}")

        self.bind("<ButtonPress-1>", start_drag)
        self.bind("<B1-Motion>", do_drag)

    def _bind_hotkeys(self):
        """Register global hotkeys from config."""
        try:
            launch_key = self.config.get("hotkey_launch_client", "ctrl+alt+c")
            toggle_key = self.config.get("hotkey_toggle_automation", "ctrl+shift+alt+a")
            compact_key = self.config.get("hotkey_compact_mode", "ctrl+shift+m")

            if launch_key:
                keyboard.add_hotkey(launch_key, self._hotkey_launch_client, suppress=False)
                self._launch_hotkey = launch_key
            if toggle_key:
                keyboard.add_hotkey(toggle_key, self._hotkey_toggle_automation, suppress=False)
                self._automation_hotkey = toggle_key
            if compact_key:
                keyboard.add_hotkey(compact_key, self._hotkey_compact, suppress=False)
                self._queue_hotkey = compact_key
            Logger.info("SYS", f"Hotkeys bound: launch={launch_key}, toggle={toggle_key}, compact={compact_key}")
        except Exception as e:
            Logger.warning("SYS", f"Hotkey bind failed: {e}")

    #: What the Riot Client needs to be told to actually open League.
    #: Started bare it initialises, finds no product to show, and exits again
    #: — which looks exactly like "the button does nothing", and was.
    LEAGUE_LAUNCH_ARGS = (
        "--launch-product=league_of_legends",
        "--launch-patchline=live",
    )

    def _hotkey_launch_client(self, launch_league: bool = True):
        """Start the Riot Client, and ask it to open League.

        `RiotClientServices.exe` with no arguments does not open anything.
        The product and patchline flags are how every other launcher does
        this, and without them the client came up headless or not at all.

        Falls back to `LeagueClient.exe` only when the Riot Client cannot be
        found: launching League directly makes the Riot Client start it
        anyway, but it is the longer road and skips the account layer.
        """
        try:
            riot = get_riot_executable_path()
            if riot and os.path.exists(riot):
                command = [riot]
                if launch_league:
                    command.extend(self.LEAGUE_LAUNCH_ARGS)
                subprocess.Popen(command, shell=False)
                Logger.action(
                    "SYS", "Launching the Riot Client.",
                    exe=riot, league=launch_league,
                )
                if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                    self.sidebar.update_action_log("Launching Riot Client...")
                return

            league = get_league_executable_path()
            if league and os.path.exists(league):
                subprocess.Popen([league], shell=False)
                Logger.action(
                    "SYS",
                    "Riot Client not found; launched League directly.",
                    exe=league,
                )
                if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                    self.sidebar.update_action_log("Launching League...")
                return

            # Say which paths were tried. "No executable found" on its own
            # gives the user nothing to check.
            Logger.error(
                "SYS",
                "Could not find RiotClientServices.exe or LeagueClient.exe. "
                "Checked the standard install path and the registry.",
            )
            if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                self.sidebar.update_action_log(
                    "Could not find the Riot Client on this PC."
                )
        except Exception as exc:
            Logger.error("SYS", "Could not launch the client.", exc=exc)
            if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                self.sidebar.update_action_log("Launching the client failed.")

    def _hotkey_toggle_automation(self):
        """Toggle automation power via hotkey."""
        try:
            if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                self.after(0, self.sidebar._on_power_click)
        except Exception as e:
            Logger.debug("SYS", f"Toggle automation hotkey: {e}")

    def _hotkey_find_match(self):
        """Find match via hotkey or remote API."""
        try:
            if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                self.after(0, self.sidebar._find_match)
        except Exception as e:
            Logger.debug("SYS", f"Find match hotkey: {e}")


    def _hotkey_compact(self):
        """Toggle compact/orb mode."""
        try:
            if hasattr(self, "mini_player"):
                self.after(0, lambda: self.mini_player.toggle() if hasattr(self.mini_player, "toggle") else None)
        except Exception as e:
            Logger.debug("SYS", f"Compact hotkey: {e}")

    def connection_loop(self):
        """Poll LCU connection and keep state in sync."""
        while self.running:
            try:
                was = self.lcu.is_connected
                self.lcu.connect(silent=True)
                now = self.lcu.is_connected
                if was != now and hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                    status = "Connected" if now else "Disconnected"
                    self.after(0, lambda s=status: self.sidebar.update_action_log(f"LCU {s}") if hasattr(self.sidebar, "update_action_log") else None)
            except Exception as e:
                Logger.debug("LCU", f"connection_loop: {e}")
                time.sleep(CONNECTION_ERROR_INTERVAL)
                continue
            time.sleep(CONNECTION_POLL_INTERVAL)

    def docking_loop(self):
        """Companion docking loop that keeps the window anchored to the League Client."""
        from services.client_window_tracker import ClientWindowTracker
        tracker = ClientWindowTracker()
        last_pos = None
        last_minimized = False

        while self.running:
            try:
                if not self.config.get("docked", True):
                    time.sleep(DOCKING_IDLE_INTERVAL)
                    continue

                window = tracker.tick()
                if not window.found or not window.visible:
                    time.sleep(DOCKING_IDLE_INTERVAL)
                    continue

                if window.minimized:
                    if not last_minimized:
                        last_minimized = True
                        self.after(0, self.withdraw)
                    time.sleep(DOCKING_POLL_INTERVAL)
                    continue
                elif last_minimized:
                    last_minimized = False
                    if not self._manually_hidden:
                        self.after(0, lambda: (self.deiconify(), self.lift()))

                # Determine docked position
                client_x, client_y, client_w, client_h = window.rect
                if client_w <= 0 or client_h <= 0:
                    time.sleep(DOCKING_IDLE_INTERVAL)
                    continue

                app_w = self.winfo_width() or SIDEBAR_WIDTH
                app_h = self.winfo_height() or SIDEBAR_HEIGHT
                gap = 4

                # Screen width probe
                screen_w = self.winfo_screenwidth() or 1920
                target_x = client_x + client_w + gap
                if target_x + app_w > screen_w:
                    target_x = max(0, client_x - app_w - gap)

                target_y = max(0, client_y)

                if (last_pos is None
                        or abs(target_x - last_pos[0]) >= GEOMETRY_THRESHOLD
                        or abs(target_y - last_pos[1]) >= GEOMETRY_THRESHOLD):
                    last_pos = (target_x, target_y)
                    self.after(0, lambda tx=target_x, ty=target_y: self.geometry(f"+{tx}+{ty}"))

                time.sleep(DOCKING_POLL_INTERVAL)
            except Exception as e:
                Logger.debug("Main", f"docking_loop exception: {e}")
                time.sleep(DOCKING_IDLE_INTERVAL)

    def _handle_window_state(self, state):
        """React to automation window state changes (hide/show/orb)."""
        try:
            if state == "hide":
                self.withdraw()
            elif state == "show":
                self.deiconify()
                self.lift()
            elif state == "orb" and hasattr(self, "mini_player"):
                self.withdraw()
                if hasattr(self.mini_player, "show"):
                    self.mini_player.show()
        except Exception as e:
            Logger.debug("UI", f"window state {state}: {e}")

    def on_settings_saved(self):
        """Rebind hotkeys after settings change."""
        try:
            keyboard.unhook_all()
            self._bind_hotkeys()
        except Exception as e:
            Logger.debug("SYS", f"settings rebind: {e}")

    def on_dock_toggled(self, docked):
        self.config.set("docked", bool(docked))

    def _show_mobile_qr(self):
        """Placeholder for mobile QR display."""
        Logger.info("SYS", f"Mobile API at http://{self._local_ip}:{self._local_port}")


def _kill_other_instances():
    """Terminate any other running instances of LeagueLoop."""
    try:
        import psutil  # type: ignore
        current_proc = psutil.Process(os.getpid())
        ignored_pids = {current_proc.pid}
        try:
            for parent in current_proc.parents():
                ignored_pids.add(parent.pid)
        except Exception as exc:
            Logger.debug("Main", "_kill_other_instances suppressed an error", exc=exc)

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["pid"] in ignored_pids:
                    continue
                name = (proc.info.get("name") or "").lower()
                cmdline = proc.info.get("cmdline") or []
                is_match = False
                if "leagueloop.exe" in name:
                    is_match = True
                elif "python" in name:
                    # Check script arguments (excluding python binary path in cmdline[0])
                    for arg in cmdline[1:]:
                        arg_str = str(arg).lower()
                        if arg_str.endswith("run.py") or arg_str.endswith("main.py") or "src.core.main" in arg_str or "core.main" in arg_str:
                            is_match = True
                            break
                if is_match:
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as exc:
        Logger.debug("Main", "_kill_other_instances suppressed an error", exc=exc)
