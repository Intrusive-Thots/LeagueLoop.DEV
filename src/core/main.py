"""
Entry point for LeagueLoop application.
"""
import os
import sys
import threading
import time
import traceback
import queue

from PySide6.QtCore import QObject, QTimer

from services.api_handler import LCUClient  # type: ignore
from services.asset_manager import AssetManager, ConfigManager  # type: ignore
from services.automation import AutomationEngine  # type: ignore
from services.account_manager import get_account_manager  # type: ignore
from services.stats_scraper import get_stats_scraper  # type: ignore
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
    CONNECTION_POLL_INTERVAL, CONNECTION_ERROR_INTERVAL,
)

from core.hotkey_manager import HotkeyManagerMixin

class LeagueLoopApp(HotkeyManagerMixin, QObject):
    """Main application service coordinator for LeagueLoop (headless controller)."""
    def __init__(self):
        """Initializes the LeagueLoopApp services."""
        super().__init__()
        
        self.config = ConfigManager()
        self.assets = AssetManager()
        from core.state import State
        State.assets = self.assets
        self.lcu = LCUClient()
        self.scraper = get_stats_scraper(mode=self.config.get("aram_mode", "ARAM"))
        
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
        self._stop_event = threading.Event()

        # Subscribe to EventBus events
        EventBus.on("action:find_match", lambda: self.after(0, self._hotkey_find_match))
        EventBus.on("action:launch_client", lambda: self.after(0, self._hotkey_launch_client))
        EventBus.on("action:toggle_automation", lambda: self.after(0, self._hotkey_toggle_automation))
        EventBus.on("action:set_status", lambda msg: threading.Thread(target=lambda: self.automation.set_custom_status(msg), daemon=True).start() if self.automation else None)
        EventBus.on("action:mass_invite", lambda: threading.Thread(target=lambda: self.automation.mass_invite_friends(), daemon=True).start() if self.automation else None)
        EventBus.on("settings_saved", lambda: self.after(0, self.on_settings_saved))

        self.automation = AutomationEngine(
            self.lcu,
            self.assets,
            self.config,
            log_func=lambda msg: Logger.info("Auto", msg),
            stop_func=lambda: self.after(0, self._hotkey_toggle_automation),
        )

        # Initialize account manager
        self.account_manager = get_account_manager(
            lcu=self.lcu,
            launch_client_func=self._hotkey_launch_client
        )

        # Keyboard shortcuts
        self._launch_hotkey = None
        self._automation_hotkey = None
        self._queue_hotkey = None
        self._bind_hotkeys()

        if self.automation is not None:
            self.automation.start(start_paused=False)  # type: ignore

        self.assets.start_loading()
            
        # Start background API server
        self._local_ip, self._local_port = start_api_server(self, port=8337)

        threading.Thread(target=self.connection_loop, daemon=True).start()
        
        # Auto-load default account on startup
        self.after(2000, self._auto_load_default_account)
        
    def _auto_load_default_account(self):
        """Auto-load default account if client is not connected on startup."""
        if not self.lcu.is_connected:
            default_idx = self.account_manager.get_default_account_index()
            if default_idx >= 0:
                Logger.info("SYS", "Auto-loading default account...")
                
                # Check if Riot Client is already running; if not, launch it first!
                if not self.account_manager.riot_client.is_riot_client_running():
                    self._hotkey_launch_client()
                    
                # Schedule login_account after a brief pause to let client launch
                self.after(3000, lambda: self.account_manager.login_account(
                    default_idx,
                    log_func=Logger.info
                ))

    def after(self, ms, func=None, *args):
        """Thread-safe replacement for Tkinter after using Qt QTimer."""
        if func is None:
            return
        
        def callback():
            try:
                func(*args)
            except Exception as e:
                Logger.error("SYS", f"Error in deferred after call: {e}")
                
        QTimer.singleShot(ms, callback)

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
        while self.running and not self._stop_event.is_set():
            try:
                if not self.lcu.is_connected:
                    connected = self.lcu.connect()
                    if connected:
                        Logger.info("LCU", "Connected to League Client")
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
                self.window_service.stop()
        except Exception as e:
            Logger.debug("SYS", f"WindowService stop error: {e}")

        # 2. Unhook keyboard hotkeys
        try:
            keyboard.unhook_all()
        except Exception as e:
            Logger.debug("SYS", f"Unhook error: {e}")

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
