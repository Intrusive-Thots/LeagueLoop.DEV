"""
LCU API Handler
Manages communication with the League of Legends Client Update (LCU).
"""
import base64
import os
import sys
import threading
import time
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor

import psutil
import requests
import urllib3
import warnings
import json
import ssl
from websockets.sync.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from utils.logger import Logger
from utils.client_detector import scan_clients


class LCUClient:
    """
    Handles communication with the Local League Client Update (LCU) API.
    Auto-detects the client's lockfile to get port and authentication.
    """

    def __init__(self):
        """Initializes the LCUClient with default values."""
        self._lock = threading.Lock()
        self.port: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.protocol: str = "https"
        self.base_url: Optional[str] = None
        self.is_connected: bool = False
        self.headers: Dict[str, str] = {}
        self.session = requests.Session()
        self.session.verify = False
        
        # 3.2 Connection pooling
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=1)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self._client_pid: Optional[int] = None
        
        # 3.1 & 3.3 State
        self._backoff = 1.0
        self._last_scan_time = 0.0
        
        self._tokens = 20.0
        self._token_capacity = 20.0
        self._token_rate = 5.0
        self._last_token_update = time.time()
        self._rate_lock = threading.Lock()
        
        # 3.5 Offline Retry Queue
        self._offline_queue = []
        self._offline_queue_max = 50  # Item #179: Prevent unbounded growth
        
        # WebSocket internals
        self._subscriptions = {}  # event_name -> list of callbacks
        self._ws_thread = None
        self._ws_should_run = False
        self._ws_connection = None
        self._ws_executor = ThreadPoolExecutor(max_workers=4)

        # Do NOT connect immediately to avoid blocking UI startup.
        # Connection is handled by the background loop in main.py.

    def connect(self, silent=False) -> bool:
        """Attempts to read the lockfile and establish connection details."""
        with self._lock:
            # Atomic check: If we connected while waiting for lock, return success
            if self.is_connected:
                return True

            try:
                # Check connection throttling
                now = time.time()
                if now - self._last_scan_time < self._backoff:
                    return False
                self._last_scan_time = now

                # Use unified client scanner
                clients = scan_clients()
                league_info = clients.get("league", {})
                
                if not league_info.get("connected"):
                    if not silent:
                        Logger.debug("LCU", "League Client not found or not connected.")
                    if self.is_connected:
                        from core.events import EventBus
                        EventBus.emit("lcu_connected", False)
                    self.is_connected = False
                    self._backoff = min(self._backoff * 1.5, 30.0)
                    return False

                self.port = league_info["port"]
                self.auth_token = league_info["token"]
                self._client_pid = league_info["pid"]

                if self.port and self.auth_token:
                    auth_str = f"riot:{self.auth_token}"
                    b64_auth = base64.b64encode(auth_str.encode()).decode()
                    self.headers = {
                        "Authorization": f"Basic {b64_auth}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    }
                    self.session.headers.update(self.headers)
                    self.base_url = f"https://127.0.0.1:{self.port}"
                    self.is_connected = True
                    self._backoff = 1.0  # Reset backoff on success
                    from core.events import EventBus
                    EventBus.emit("lcu_connected", True)
                    Logger.debug("LCU", f"Connected to port {self.port}")
                    return True

                Logger.debug("LCU", "Found League Client but credentials are missing.")

            except Exception as e:
                Logger.error("LCU", f"Connection Error: {e}")
                if self.is_connected:
                    from core.events import EventBus
                    EventBus.emit("lcu_connected", False)
                self.is_connected = False

            return False

    def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        silent: bool = False,
    ) -> Optional[requests.Response]:
        """Generic wrapper for LCU requests."""
        if not self.is_connected:
            if not self.connect(silent=silent):
                if method in ["POST", "PUT", "PATCH", "DELETE"]:
                    # 3.5 Offline Retry Queue: save state mutations for when we reconnect
                    # Item #179: Cap queue size to prevent unbounded growth
                    if len(self._offline_queue) < self._offline_queue_max:
                        self._offline_queue.append((method, endpoint, data))
                return None

        # Flush 3.5 Offline Retry Queue on successful connection
        with self._lock:
            oq = self._offline_queue.copy()
            self._offline_queue.clear()
        if oq:
            # Item #177: Use bounded executor instead of spawning raw threads
            for m, e, d in oq:
                self._ws_executor.submit(self.request, m, e, d, True)

        # 3.3 Strict Token Bucket Rate-Limiter
        # Item #178: Calculate sleep time inside lock, but sleep outside to prevent deadlock
        sleep_time = 0.0
        with self._rate_lock:
            now = time.time()
            self._tokens = min(self._token_capacity, self._tokens + (now - self._last_token_update) * self._token_rate)
            self._last_token_update = now
            if self._tokens < 1.0:
                sleep_time = (1.0 - self._tokens) / self._token_rate
                self._tokens = 0.0
                self._last_token_update = time.time()
            else:
                self._tokens -= 1.0
        if sleep_time > 0:
            time.sleep(sleep_time)

        url = f"{self.base_url}{endpoint}"
        t_start = time.time()
        try:
            if not silent:
                Logger.debug("LCU", f"REQ -> {method} {endpoint}")
            
            # TRACE payload format
            if endpoint == "/lol-lobby/v2/lobby" and method == "POST":
                Logger.debug("LCU_TRACE", f"DATA TYPE: {type(data)} | RAW: {data}")
                
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    verify=False,
                    timeout=2,  # Prevent blocking UI
                )

            dur = time.time() - t_start
            if not silent:
                Logger.debug(
                    "LCU", f"RES <- {response.status_code} [{dur:.3f}s] {endpoint}"
                )
            return response
        except requests.exceptions.ConnectionError:
            # Expected when the game is closed or restarting
            self.is_connected = False
            return None
        except requests.exceptions.ReadTimeout:
            # Expected for long-polling endpoints
            return None
        except requests.RequestException as e:
            dur = time.time() - t_start
            Logger.error("LCU", f"FAIL [{dur:.3f}s] {endpoint} : {e}")
            # Connection lost?
            self.is_connected = False
            return None

    # ─────────── WEBSOCKET PUBLISH / SUBSCRIBE ───────────

    def start_websocket(self):
        """Starts the persistent websocket thread if not running."""
        if self._ws_thread and self._ws_thread.is_alive():
            return
        
        self._ws_should_run = True
        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._ws_thread.start()

    def stop_websocket(self):
        """Stops the websocket thread."""
        self._ws_should_run = False
        if self._ws_connection:
            try:
                self._ws_connection.close()
            except Exception as e:
                Logger.debug("LCU_WS", f"WS close error (safe to ignore): {e}")
        # Item #181: Join thread with timeout for clean shutdown
        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=3)

    def subscribe(self, event_name: str, callback):
        """Subscribes an event callback to the LCU WAMP WebSocket."""
        with self._lock:
            if event_name not in self._subscriptions:
                self._subscriptions[event_name] = []
                self._server_subscribe(event_name)
            if callback not in self._subscriptions[event_name]:
                self._subscriptions[event_name].append(callback)

    def _server_subscribe(self, event_name: str):
        if self._ws_connection:
            try:
                msg = [5, event_name]
                self._ws_connection.send(json.dumps(msg))
            except Exception as e:
                Logger.error("LCU_WS", f"Subscribe error: {e}")

    def _ws_loop(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        while self._ws_should_run:
            if not self.is_connected or not self.port or not self.auth_token:
                time.sleep(2)
                continue
            
            auth_str = f"riot:{self.auth_token}"
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            headers = {"Authorization": f"Basic {b64_auth}"}

            uri = f"wss://127.0.0.1:{self.port}"
            try:
                with ws_connect(uri, ssl=ctx, additional_headers=headers) as ws:
                    self._ws_connection = ws
                    Logger.debug("LCU_WS", "WebSocket connected.")
                    
                    # Re-subscribe to all existing subscriptions
                    with self._lock:
                        for ev in self._subscriptions:
                            try:
                                msg = [5, ev]
                                ws.send(json.dumps(msg))
                            except Exception as e:
                                Logger.debug("LCU_WS", f"WS subscribe send failed: {e}")

                    while self._ws_should_run:
                        # Item #180: Use timeout to prevent blocking forever on stale connections
                        try:
                            message = ws.recv(timeout=30)
                        except TimeoutError:
                            continue
                        if not message:
                            continue
                            
                        # WAMP v1 is JSON array
                        try:
                            # [8, "OnJsonApiEvent...", payload]
                            data = json.loads(message)
                            if isinstance(data, list) and len(data) >= 3 and data[0] == 8:
                                event_name = data[1]
                                payload = data[2]
                                
                                # 3.4 WAMP auto-normalization
                                try:
                                    if isinstance(payload, dict) and 'data' in payload and 'eventType' in payload:
                                        payload = payload['data']  # Normalize nested WAMP payload to flat data
                                except Exception as e:
                                    Logger.debug("LCU_WS", f"WAMP payload normalization failed: {e}")

                                # Emit to central EventBus (Phase 2 Rule)
                                from core.events import EventBus
                                EventBus.emit(event_name, payload)

                                # Find callbacks
                                callbacks = []
                                with self._lock:
                                    if event_name in self._subscriptions:
                                        callbacks = self._subscriptions[event_name].copy()
                                    if "OnJsonApiEvent" in self._subscriptions:
                                        callbacks.extend(self._subscriptions["OnJsonApiEvent"])
                                
                                for cb in callbacks:
                                    try:
                                        # Run callback in bounded pool so we don't stall the websocket
                                        self._ws_executor.submit(cb, event_name, payload)
                                    except Exception as e:
                                        Logger.error("LCU_WS", f"Callback error in {event_name}: {e}")

                        except json.JSONDecodeError:
                            pass
                        except Exception as e:
                            Logger.error("LCU_WS", f"Message parse error: {e}")

            except ConnectionClosed:
                Logger.debug("LCU_WS", "WebSocket closed normally or by server.")
            except Exception as e:
                Logger.debug("LCU_WS", f"WebSocket connection failed: {e}")
            
            self._ws_connection = None
            time.sleep(3)  # Reconnect delay
