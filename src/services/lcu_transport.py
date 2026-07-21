"""
Riot LCU Transport Module
Provides hardened LCU transport layer with connection pooling, exponential backoff retries, and typed connection event dispatch.
"""
import base64
import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

import requests
import urllib3
import warnings

from core.events import EventBus, LCUConnectionEvent
from utils.logger import Logger
from utils.client_detector import scan_clients

# Suppress insecure HTTPS warning for LCU self-signed cert on 127.0.0.1
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)


class LCUTransport:
    """
    Hardened LCU Transport handling lockfile resolution, connection pooling,
    exponential backoff retries, and typed event notifications.
    """

    def __init__(self, max_retries: int = 3):
        self.port: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.protocol: str = "https"
        self.base_url: Optional[str] = None
        self.is_connected: bool = False
        self.headers: Dict[str, str] = {}
        
        self._max_retries = max_retries
        self._lock = threading.Lock()
        self._backoff = 1.0
        self._last_scan_time = 0.0

        self.session = requests.Session()
        self.session.verify = False
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=1)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def connect(self, silent: bool = False) -> bool:
        """Resolves LCU credentials and establishes connection session."""
        with self._lock:
            if self.is_connected:
                return True

            try:
                now = time.time()
                if now - self._last_scan_time < self._backoff:
                    return False
                self._last_scan_time = now

                clients = scan_clients()
                league_info = clients.get("league", {})

                if not league_info.get("connected"):
                    if not silent:
                        Logger.debug("LCUTransport", "League Client lockfile not detected.")
                    if self.is_connected:
                        self.is_connected = False
                        EventBus.publish(LCUConnectionEvent(connected=False))
                        EventBus.emit("lcu_connected", False)
                    self._backoff = min(self._backoff * 1.5, 10.0)
                    return False

                self.port = str(league_info.get("port", ""))
                self.auth_token = str(league_info.get("token") or league_info.get("auth_token", ""))
                self.base_url = f"{self.protocol}://127.0.0.1:{self.port}"

                auth_header = base64.b64encode(f"riot:{self.auth_token}".encode("utf-8")).decode("utf-8")
                self.headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Basic {auth_header}",
                }
                self.session.headers.update(self.headers)

                # Test connection endpoint
                res = self.session.get(f"{self.base_url}/lol-gameflow/v1/gameflow-phase", timeout=2.0)
                if res.status_code in (200, 404):
                    self.is_connected = True
                    self._backoff = 1.0
                    if not silent:
                        Logger.info("LCUTransport", f"Successfully connected to LCU at {self.base_url}")
                    EventBus.publish(LCUConnectionEvent(connected=True, port=int(self.port)))
                    EventBus.emit("lcu_connected", True)
                    return True
                
                self.is_connected = False
                return False

            except Exception as e:
                if not silent:
                    Logger.debug("LCUTransport", f"Connection attempt failed: {e}")
                self.is_connected = False
                self._backoff = min(self._backoff * 1.5, 10.0)
                return False

    def request(self, method: str, endpoint: str, data: Optional[Any] = None, silent: bool = False, *args, **kwargs) -> Optional[requests.Response]:
        """
        Executes HTTP request with exponential backoff retry logic.
        """
        if not self.is_connected or not self.base_url:
            if not silent:
                Logger.debug("LCUTransport", f"Request ignored — LCU disconnected: {endpoint}")
            return None

        url = f"{self.base_url}{endpoint}"
        retries = 0
        backoff_delay = 0.5

        while retries <= self._max_retries:
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    json=data if isinstance(data, (dict, list)) else None,
                    data=data if isinstance(data, str) else None,
                    timeout=kwargs.get("timeout", 4.0),
                )
                return response
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                retries += 1
                if retries > self._max_retries:
                    if not silent:
                        Logger.error("LCUTransport", f"Request failed after {retries} retries ({method} {endpoint}): {e}")
                    self.is_connected = False
                    EventBus.publish(LCUConnectionEvent(connected=False))
                    EventBus.emit("lcu_connected", False)
                    return None
                time.sleep(backoff_delay)
                backoff_delay *= 2.0
            except Exception as e:
                if not silent:
                    Logger.error("LCUTransport", f"Unexpected request error ({method} {endpoint}): {e}")
                return None

        return None
