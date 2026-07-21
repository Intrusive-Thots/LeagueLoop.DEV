"""
Application Lifecycle Manager
Handles application startup, background connection threads, API server lifecycle, and clean shutdown.
"""
import os
import threading
import time
from typing import Optional

from PySide6.QtCore import QObject, QTimer

from core.container import ApplicationContainer
from core.events import EventBus
from core.constants import CONNECTION_POLL_INTERVAL, CONNECTION_ERROR_INTERVAL
from services.api import start_api_server
from utils.logger import Logger

try:
    import keyboard
except ImportError:
    keyboard = None


class ApplicationManager(QObject):
    """Central manager overseeing service lifecycle, background workers, and clean exit."""

    def __init__(self, container: Optional[ApplicationContainer] = None):
        super().__init__()
        self.container = container or ApplicationContainer()
        self.running = False
        self._stop_event = threading.Event()
        self.api_ip: Optional[str] = None
        self.api_port: Optional[int] = None
        self._conn_thread: Optional[threading.Thread] = None

    def startup(self, launch_client_func=None, toggle_automation_func=None, find_match_func=None):
        """Starts all subsystem background services, API server, and connection monitoring."""
        Logger.info("Lifecycle", "Starting ApplicationManager services...")
        self.running = True
        self._stop_event.clear()

        # Initialize WindowService
        self.container.window_service.start()

        # Initialize AutomationEngine
        self.container.initialize_automation(stop_callback=toggle_automation_func)

        # Initialize AccountManager
        self.container.initialize_account_manager(launch_client_func=launch_client_func)

        # Subscribe to EventBus events
        if find_match_func:
            EventBus.on("action:find_match", lambda: QTimer.singleShot(0, find_match_func))
        if launch_client_func:
            EventBus.on("action:launch_client", lambda: QTimer.singleShot(0, launch_client_func))
        if toggle_automation_func:
            EventBus.on("action:toggle_automation", lambda: QTimer.singleShot(0, toggle_automation_func))
        
        EventBus.on("action:set_status", lambda msg: threading.Thread(
            target=lambda: self.container.automation.set_custom_status(msg), daemon=True
        ).start() if self.container.automation else None)
        
        EventBus.on("action:mass_invite", lambda: threading.Thread(
            target=lambda: self.container.automation.mass_invite_friends(), daemon=True
        ).start() if self.container.automation else None)
        
        EventBus.on("settings_saved", self.on_settings_saved)

        # Start automation engine loop
        if self.container.automation:
            self.container.automation.start(start_paused=False)

        # Start asset loading
        self.container.assets.start_loading()

        # Start background API server
        try:
            self.api_ip, self.api_port = start_api_server(self.container, port=8337)
        except Exception as e:
            Logger.error("Lifecycle", f"Failed to start API server: {e}")

        # Start connection loop thread
        self._conn_thread = threading.Thread(target=self._connection_loop, daemon=True)
        self._conn_thread.start()

    def on_settings_saved(self):
        """Handles settings saved event."""
        self.container.scraper.set_mode(self.container.config.get("aram_mode", "ARAM"))

    def toggle_power(self, power_state: bool):
        """Toggles automation engine pause/resume state."""
        Logger.info("Lifecycle", f"Power Toggled: {power_state}")
        if self.container.automation:
            if power_state:
                self.container.automation.resume()
            else:
                self.container.automation.pause()

    def _connection_loop(self):
        """Background thread loop maintaining connection with League Client LCU API."""
        while self.running and not self._stop_event.is_set():
            try:
                if not self.container.lcu.is_connected:
                    connected = self.container.lcu.connect()
                    if connected:
                        Logger.info("LCU", "Connected to League Client")
                time.sleep(CONNECTION_POLL_INTERVAL)
            except Exception as e:
                Logger.error("Lifecycle", f"Connection loop error: {e}")
                time.sleep(CONNECTION_ERROR_INTERVAL)

    def shutdown(self):
        """Shuts down all subsystem background threads, unhooks hotkeys, and exits."""
        Logger.info("Lifecycle", "Shutdown requested — terminating services...")
        self.running = False
        self._stop_event.set()

        try:
            if self.container.automation:
                self.container.automation.stop()
        except Exception as e:
            Logger.debug("Lifecycle", f"Engine stop error: {e}")

        try:
            if self.container.window_service:
                self.container.window_service.stop()
        except Exception as e:
            Logger.debug("Lifecycle", f"WindowService stop error: {e}")

        if keyboard:
            try:
                keyboard.unhook_all()
            except Exception as e:
                Logger.debug("Lifecycle", f"Keyboard unhook error: {e}")

        Logger.info("Lifecycle", "Shutdown sequence finished.")
        os._exit(0)
