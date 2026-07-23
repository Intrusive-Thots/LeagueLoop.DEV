"""
Entry point for LeagueLoop application.
"""
import os
import sys
import threading
import time

from PySide6.QtCore import QObject, QTimer

from core.container import ApplicationContainer
from core.lifecycle import ApplicationManager
from core.hotkey_manager import HotkeyManagerMixin
from core.version import __version__
from utils.logger import Logger

try:
    import keyboard
except ImportError:
    keyboard = None


class LeagueLoopApp(HotkeyManagerMixin, QObject):
    """Main application controller delegating to ApplicationContainer and ApplicationManager."""

    def __init__(self):
        super().__init__()
        
        self.container = ApplicationContainer()
        self.lifecycle = ApplicationManager(self.container)
        
        # Expose legacy property aliases for backwards compatibility with legacy routes/views
        self.config = self.container.config
        self.assets = self.container.assets
        self.lcu = self.container.lcu
        self.scraper = self.container.scraper
        self.settings_service = self.container.settings_service
        self.league_service = self.container.league_service
        self.friend_service = self.container.friend_service
        self.champion_service = self.container.champion_service
        self.draft_service = self.container.draft_service
        self.window_service = self.container.window_service
        self.notification_service = self.container.notification_service
        self.queue_service = self.container.queue_service
        
        # Keyboard shortcuts
        self._launch_hotkey = None
        self._automation_hotkey = None
        self._queue_hotkey = None

        # Start lifecycle services
        self.lifecycle.startup(
            launch_client_func=self._hotkey_launch_client,
            toggle_automation_func=self._hotkey_toggle_automation,
            find_match_func=self._hotkey_find_match,
        )

        self.automation = self.container.automation
        self.account_manager = self.container.account_manager

        self._bind_hotkeys()
        
        # Auto-load default account on startup
        QTimer.singleShot(2000, self._auto_load_default_account)

    def _auto_load_default_account(self):
        """Auto-load default account if client is not connected on startup."""
        try:
            if not self.lcu.is_connected and self.account_manager:
                default_idx = self.account_manager.get_default_account_index()
                if default_idx >= 0:
                    pwd = self.account_manager.get_password(default_idx)
                    if pwd:
                        Logger.info("SYS", "Auto-loading default account...")
                        if not self.account_manager.riot_client.is_riot_client_running():
                            self._hotkey_launch_client()
                            
                        QTimer.singleShot(3000, lambda: self.account_manager.login_account(
                            default_idx,
                            log_func=Logger.info
                        ))
        except Exception as e:
            Logger.error("SYS", f"Auto-load default account failed: {e}")

    def on_settings_saved(self):
        """Handles settings saved event."""
        self._bind_hotkeys()
        self.lifecycle.on_settings_saved()

    def toggle_power(self, power_state):
        """Toggles automation engine pause/resume state."""
        self.lifecycle.toggle_power(power_state)

    def _on_close(self):
        """Requests application shutdown via LifecycleManager."""
        self.lifecycle.shutdown()


def _kill_other_instances():
    """Terminate any other running instances of LeagueLoop."""
    import psutil
    my_pid = os.getpid()
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
            
            Logger.info("SYS", f"Killing stale instance PID {proc.pid} ({pname})")
            proc.kill()
            killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    if killed:
        Logger.info("SYS", f"Terminated {killed} stale instance(s).")
        time.sleep(0.3)
