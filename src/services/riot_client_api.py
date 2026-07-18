"""
Riot Client API Service
───────────────────────
Connects to the local Riot Client (RiotClientServices.exe) API.
"""
import base64
import warnings
from typing import Optional

import requests
import urllib3

from utils.logger import Logger
from utils.client_detector import scan_clients

class RiotClientAPI:
    """Connects to the local Riot Client (RiotClientServices.exe) API."""

    def __init__(self):
        self.port: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.base_url: Optional[str] = None
        self.session = requests.Session()
        self.session.verify = False
        self.is_connected = False

    def connect(self) -> bool:
        """Find and connect to the Riot Client's local API."""
        try:
            clients = scan_clients()
            riot_info = clients.get("riot", {})
            if riot_info.get("connected"):
                self._set_credentials(riot_info["port"], riot_info["token"])
                return True
        except Exception as e:
            Logger.debug("RiotClientAPI", f"Connection scan failed: {e}")
        self.is_connected = False
        return False

    def _set_credentials(self, port: str, token: str):
        """Configure the session with Riot Client API credentials."""
        self.port = port
        self.auth_token = token
        self.base_url = f"https://127.0.0.1:{port}"

        auth_str = f"riot:{token}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        self.session.headers.update({
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self.is_connected = True
        Logger.debug("RiotClientAPI", f"Connected to Riot Client on port {port}")

    def request(self, method: str, endpoint: str, data=None, silent=False) -> Optional[requests.Response]:
        """Make a request to the Riot Client API."""
        if not self.is_connected:
            if not self.connect():
                return None

        url = f"{self.base_url}{endpoint}"
        try:
            if not silent:
                Logger.debug("RiotClientAPI", f"REQ -> {method} {endpoint}")

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    verify=False,
                    timeout=10,
                )

            if not silent:
                Logger.debug("RiotClientAPI", f"RES <- {response.status_code} {endpoint}")
            return response
        except requests.exceptions.ConnectionError:
            self.is_connected = False
            return None
        except Exception as e:
            Logger.error("RiotClientAPI", f"Request failed: {e}")
            self.is_connected = False
            return None

    def sign_out(self) -> bool:
        """
        Sign out the current account via the Riot Client API.
        NOTE: This will FAIL with 'sign_out_failed_other_games_running'
        if LeagueClient.exe is still running. Caller must kill it first.
        """
        res = self.request("DELETE", "/rso-auth/v1/session")
        if res and res.status_code in [200, 204]:
            Logger.info("RiotClientAPI", "Signed out successfully")
            return True

        # Log the actual error for debugging
        if res:
            try:
                body = res.json()
                msg = body.get("message", "")
                Logger.warning("RiotClientAPI", f"Sign out failed ({res.status_code}): {msg}")
            except Exception:
                Logger.warning("RiotClientAPI", f"Sign out failed: {res.status_code}")
        else:
            Logger.warning("RiotClientAPI", "Sign out failed: no response")
        return False

    def sign_in(self, username: str, password: str, persist: bool = False) -> dict:
        """
        Sign in with username/password via the Riot Client authenticator.
        Uses PUT /rso-authenticator/v1/authentication.
        Returns the response body dict (caller should check 'type' and 'error' fields).
        """
        payload = {
            "username": username,
            "password": password,
            "persistLogin": persist,
            "language": "en_US",
        }
        res = self.request("PUT", "/rso-authenticator/v1/authentication", data=payload)
        if res and res.status_code in [200, 201]:
            try:
                body = res.json()
                auth_type = body.get("type", "")
                error = body.get("error", "")

                if auth_type == "success" or (auth_type == "authenticated" and not error):
                    Logger.info("RiotClientAPI", "Signed in successfully")
                    return body
                elif auth_type == "multifactor":
                    Logger.info("RiotClientAPI", "Sign-in requires 2FA")
                    return body
                elif error:
                    Logger.warning("RiotClientAPI", f"Sign-in error: {error}")
                    return body
                else:
                    Logger.info("RiotClientAPI", f"Sign-in response type: {auth_type}")
                    return body
            except Exception as e:
                Logger.debug("RiotClientAPI", f"Failed to parse sign-in response: {e}")
                return {"type": "error", "error": "unparseable_response"}

        status = res.status_code if res else "no response"
        Logger.warning("RiotClientAPI", f"Sign-in request failed: {status}")
        return {"type": "error", "error": f"http_{status}"}

    def get_session(self) -> Optional[dict]:
        """Get the current RSO session state."""
        res = self.request("GET", "/rso-auth/v1/session", silent=True)
        if res and res.status_code == 200:
            try:
                return res.json()
            except Exception as e:
                Logger.debug("RiotClientAPI", f"Failed to parse session response: {e}")
        return None

    def get_current_user(self) -> Optional[dict]:
        """Get the currently logged-in user's info (game name, tag, etc)."""
        res = self.request("GET", "/riot-client-auth/v1/userinfo", silent=True)
        if res and res.status_code == 200:
            try:
                return res.json()
            except Exception as e:
                Logger.debug("RiotClientAPI", f"Failed to parse userinfo response: {e}")
        return None

    def get_auth_status(self) -> Optional[dict]:
        """Check the current authentication/authorization state."""
        res = self.request("GET", "/rso-auth/v1/authorization", silent=True)
        if res and res.status_code == 200:
            try:
                return res.json()
            except Exception as e:
                Logger.debug("RiotClientAPI", f"Failed to parse auth response: {e}")
        return None

    def is_signed_in(self) -> bool:
        """Check if a user is currently signed in."""
        session = self.get_session()
        if session and session.get("type") == "authenticated":
            return True
        return False

    def is_riot_client_running(self) -> bool:
        """Check if the Riot Client process is running."""
        try:
            clients = scan_clients()
            return clients.get("riot", {}).get("pid") is not None
        except Exception as e:
            Logger.debug("RiotClientAPI", f"Process scan error: {e}")
        return False
