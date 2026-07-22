"""
Discord Rich Presence Manager Module for LeagueLoop.

Provides background IPC connection management and status updates for Discord Rich Presence.
"""

import time
import threading
from typing import Optional
from pypresence import Presence # type: ignore
from utils.logger import Logger # type: ignore

# The Discord Application ID for LeagueLoop
DISCORD_CLIENT_ID = "1214041178652250162"  # Mock Discord App ID for LeagueLoop Rich Presence

class DiscordPresenceManager:
    """Manages the connection and states for Discord Rich Presence safely in the background."""

    _RECONNECT_COOLDOWN = 300  # 5 minutes between reconnect attempts

    def __init__(self, config):
        self.config = config
        self.rpc = None
        self._connected = False
        self._thread = None
        self._last_update = 0
        self._last_connect_attempt = 0.0
        self._connect_failures = 0
        self._current_state = {}

    @property
    def is_connected(self) -> bool:
        """Whether we currently have an active Discord IPC connection."""
        return self._connected

    def connect(self):
        """Attempts to connect to Discord IPC locally with exponential backoff."""
        if not self.config.get("discord_rpc_enabled", True):
            return

        if self._connected:
            return

        # Backoff: skip if we recently failed
        now = time.time()
        if self._connect_failures > 0 and (now - self._last_connect_attempt) < self._RECONNECT_COOLDOWN:
            return

        self._last_connect_attempt = now

        def _connect_worker():
            try:
                self.rpc = Presence(DISCORD_CLIENT_ID)
                self.rpc.connect()
                self._connected = True
                self._connect_failures = 0
                Logger.info("DiscordRPC", "Connected to Discord.")
                self.update_presence("Idle", "Watching the client")
            except Exception as e:
                self._connect_failures += 1
                self._connected = False
                # Only log the first failure to avoid spamming the console
                if self._connect_failures == 1:
                    Logger.debug("DiscordRPC", f"Discord not running — will retry in {self._RECONNECT_COOLDOWN}s.")

        self._thread = threading.Thread(target=_connect_worker, daemon=True)
        self._thread.start()

    def disconnect(self):
        self._connected = False
        if self.rpc:
            try:
                self.rpc.close()
            except Exception as e:
                Logger.debug("Discord", f"RPC disconnect error (safe to ignore): {e}")

    def update_presence(self, state: str, details: Optional[str] = None, start_time: int = None, party_size: list = None):
        """Updates the discord profile status, respecting ratelimits (max 1 per 15s typically)."""
        if not self.config.get("discord_rpc_enabled", True):
            return

        if not self._connected or not self.rpc:
            return

        now = time.time()
        # Discord rate limits updates. We throttle them to once every 10 seconds.
        if now - self._last_update < 10.0:
            return

        try:
            kwargs = {
                "state": state,
                "large_image": "app_icon",  # Relies on uploaded asset at discordant dev portal
                "large_text": "League Loop Tracker"
            }
            if details:
                kwargs["details"] = details
            if start_time:
                kwargs["start"] = start_time
            if party_size:
                kwargs["party_size"] = party_size

            # Deduplicate: skip update if state hasn't changed
            if kwargs == self._current_state:
                return

            self._last_update = now
            self._current_state = kwargs
            
            self.rpc.update(**kwargs)
        except Exception as e:
            Logger.debug("DiscordRPC", f"Failed to update presence: {e}")
            self._connected = False
