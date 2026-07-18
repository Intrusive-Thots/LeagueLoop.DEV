"""
Account Manager Service
───────────────────────
Manages multiple Riot account credentials with DPAPI encryption.
Handles secure storage, CRUD operations, and automated login/logout
via the Riot Client's local REST API.

The Riot Client (RiotClientServices.exe) exposes a local HTTPS API
on 127.0.0.1 with port + auth token discoverable from:
  1. Process command-line args (--app-port, --remoting-auth-token)
  2. Lockfile at %LocalAppData%/Riot Games/Riot Client/Config/lockfile

Key endpoints:
  PUT  /rso-auth/v1/session/credentials  — Sign in with username/password
  DELETE /rso-auth/v1/session            — Sign out
  GET  /rso-auth/v1/authorization        — Check auth status

Security: Passwords encrypted at rest using Windows DPAPI
(CryptProtectData), tied to the current Windows user account.
"""
import base64
import json
import os
import subprocess
import threading
import time
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional

import psutil
import requests
import urllib3
import win32crypt

from utils.logger import Logger
from utils.path_utils import get_data_dir
from utils.client_detector import scan_clients

# Storage location — intentionally separate from config.json
_DATA_DIR = get_data_dir()
ACCOUNTS_FILE = os.path.join(_DATA_DIR, "accounts.json")

# Riot Client lockfile paths
_RC_LOCKFILE_PATHS = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Riot Games", "Riot Client", "Config", "lockfile"),
]


from services.riot_client_api import RiotClientAPI


class AccountManager:
    """Manages encrypted Riot account credentials and login automation."""

    def __init__(self, lcu=None, launch_client_func=None):
        self.lcu = lcu
        self._launch_client_func = launch_client_func
        self.riot_client = RiotClientAPI()
        self._accounts: List[Dict[str, Any]] = []
        self._active_idx: int = -1
        self._lock = threading.Lock()
        
        # Migration: Ensure existing accounts have new fields
        self._load()
        self._migrate_accounts()

    def _migrate_accounts(self):
        """Ensure all loaded accounts have required fields for new features."""
        dirty = False
        for acct in self._accounts:
            if "wallet" not in acct: acct["wallet"] = {"be": 0, "rp": 0}
            if "region" not in acct: acct["region"] = "NA1"
            if "last_used" not in acct: acct["last_used"] = None
            if "is_default" not in acct: acct["is_default"] = False
            dirty = True
        if dirty:
            self._save()

    # ─────────── Encryption (DPAPI) ───────────
    @staticmethod
    def _encrypt(plaintext: str) -> str:
        """Encrypt a string using Windows DPAPI, return base64-encoded result."""
        try:
            encrypted = win32crypt.CryptProtectData(
                plaintext.encode("utf-8"),
                "LeagueLoop Account",
                None, None, None, 0
            )
            return base64.b64encode(encrypted).decode("ascii")
        except Exception as e:
            Logger.error("AccountManager", f"Encryption failed: {e}")
            return ""

    @staticmethod
    def _decrypt(encrypted_b64: str) -> str:
        """Decrypt a DPAPI-encrypted base64 string, return plaintext."""
        try:
            encrypted = base64.b64decode(encrypted_b64)
            _, decrypted = win32crypt.CryptUnprotectData(
                encrypted, None, None, None, 0
            )
            return decrypted.decode("utf-8")
        except Exception as e:
            Logger.error("AccountManager", f"Decryption failed: {e}")
            return ""

    # ─────────── Storage ───────────
    def _load(self):
        """Load accounts from disk."""
        if not os.path.exists(ACCOUNTS_FILE):
            self._accounts = []
            self._active_idx = -1
            return

        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._accounts = data.get("accounts", [])
            self._active_idx = data.get("active_account_idx", -1)
        except Exception as e:
            Logger.error("AccountManager", f"Failed to load accounts: {e}")
            self._accounts = []
            self._active_idx = -1

    def _save(self):
        """Persist accounts to disk."""
        try:
            os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
            data = {
                "accounts": self._accounts,
                "active_account_idx": self._active_idx,
            }
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            Logger.error("AccountManager", f"Failed to save accounts: {e}")

    # ─────────── CRUD ───────────
    def get_accounts(self) -> List[Dict[str, Any]]:
        """Return all accounts sorted by most recently used (last_used)."""
        def parse_date(date_str):
            if not date_str: return datetime.min
            try: return datetime.fromisoformat(date_str)
            except: return datetime.min

        with self._lock:
            # Sort a copy so we don't scramble index maps permanently,
            # or actually, just return them as-is but UI will sort?
            # Wait, if we sort the underlying array, indices change!
            # We must maintain stable indices. The UI will just use the returned list.
            # actually it's better to just sort the underlying array and update _active_idx.
            if len(self._accounts) > 1:
                active_acct = self._accounts[self._active_idx] if self._active_idx >= 0 else None
                self._accounts.sort(key=lambda a: parse_date(a.get("last_used")), reverse=True)
                if active_acct:
                    self._active_idx = self._accounts.index(active_acct)
                self._save()

        return list(self._accounts)

    def get_account_count(self) -> int:
        return len(self._accounts)

    def get_active_index(self) -> int:
        return self._active_idx

    def get_default_account_index(self) -> int:
        """Return the index of the default account, or -1 if none is set."""
        with self._lock:
            for i, acct in enumerate(self._accounts):
                if acct.get("is_default", False):
                    return i
        return -1

    def set_default_account(self, idx: int):
        """Set the account at the given index as default and clear default on others."""
        with self._lock:
            for i, acct in enumerate(self._accounts):
                acct["is_default"] = (i == idx)
            self._save()

    def add_account(self, label: str, username: str, password: str, tagline: str = "", region: str = "NA1") -> int:
        """Add a new account. Returns the index of the new account.
        
        Args:
            label: Display name for the account (e.g. 'Main')
            username: Riot login username (NOT the in-game name)
            password: Riot login password
            tagline: In-game Riot ID (e.g. 'IntrusiveThots#NTRSV'), optional
            region: The server shard region (e.g. 'NA1', 'EUW')
        """
        with self._lock:
            account = {
                "label": label.strip(),
                "username": username.strip(),
                "password_enc": self._encrypt(password),
                "tagline": tagline.strip(),
                "region": region.strip(),
                "last_used": None,
                "wallet": {"be": 0, "rp": 0},
                "is_default": False
            }
            self._accounts.append(account)
            idx = len(self._accounts) - 1
            self._save()
            return idx

    def edit_account(self, idx: int, label: str = None, username: str = None,
                     password: str = None, tagline: str = None, region: str = None, is_default: bool = None):
        """Update fields of an existing account. Only non-None fields are changed."""
        with self._lock:
            if not (0 <= idx < len(self._accounts)):
                return
            acct = self._accounts[idx]
            if label is not None:
                acct["label"] = label.strip()
            if username is not None:
                acct["username"] = username.strip()
            if password is not None:
                acct["password_enc"] = self._encrypt(password)
            if tagline is not None:
                acct["tagline"] = tagline.strip()
            if region is not None:
                acct["region"] = region.strip()
            if is_default is not None:
                if is_default:
                    for i, a in enumerate(self._accounts):
                        a["is_default"] = (i == idx)
                else:
                    acct["is_default"] = False
            self._save()

    def delete_account(self, idx: int):
        """Remove an account by index."""
        with self._lock:
            if not (0 <= idx < len(self._accounts)):
                return
            self._accounts.pop(idx)
            # Adjust active index
            if self._active_idx == idx:
                self._active_idx = -1
            elif self._active_idx > idx:
                self._active_idx -= 1
            self._save()

    def move_account(self, idx: int, direction: int):
        """Move an account up (-1) or down (+1)."""
        with self._lock:
            new_idx = idx + direction
            if not (0 <= new_idx < len(self._accounts)):
                return
            self._accounts[idx], self._accounts[new_idx] = (
                self._accounts[new_idx], self._accounts[idx]
            )
            # Track active index through the swap
            if self._active_idx == idx:
                self._active_idx = new_idx
            elif self._active_idx == new_idx:
                self._active_idx = idx
            self._save()

    def get_password(self, idx: int) -> str:
        """Decrypt and return the password for an account."""
        if not (0 <= idx < len(self._accounts)):
            return ""
        enc = self._accounts[idx].get("password_enc", "")
        if not enc:
            return ""
        return self._decrypt(enc)

    # ─────────── Active Account Detection ───────────
    def detect_active_account(self) -> int:
        """Try to detect which account is currently logged in.
        
        Data model:
          - acct['username'] = Riot login username (e.g. 'themalcolm3')
          - acct['tagline']  = In-game Riot ID (e.g. 'IntrusiveThots#NTRSV')
          - acct['label']    = User-defined label (e.g. 'Main')

        API returns:
          - preferred_username = Riot login username (matches acct['username'])
          - acct.game_name + acct.tag_line = In-game Riot ID (matches acct['tagline'])
        """
        # Method 1: Riot Client API (most reliable)
        try:
            if self.riot_client.connect():
                userinfo = self.riot_client.get_current_user()
                if userinfo:
                    riot_login = (userinfo.get("preferred_username") or "").lower()
                    acct_info = userinfo.get("acct", {}) or {}
                    game_name = (acct_info.get("game_name") or "").lower()
                    tag_line = (acct_info.get("tag_line") or "").lower()
                    # Build the full Riot ID for matching
                    riot_id = f"{game_name}#{tag_line}" if game_name and tag_line else game_name

                    for i, acct in enumerate(self._accounts):
                        acct_user = acct.get("username", "").lower()
                        acct_tag = acct.get("tagline", "").lower()
                        acct_label = acct.get("label", "").lower()

                        # Best match: Riot login username == stored username
                        if acct_user and acct_user == riot_login:
                            self._active_idx = i
                            self._save()
                            return i

                    # Second pass: match by Riot ID or label
                    for i, acct in enumerate(self._accounts):
                        acct_tag = acct.get("tagline", "").lower()
                        acct_label = acct.get("label", "").lower()

                        # Match stored Riot ID against live Riot ID
                        if acct_tag and riot_id and acct_tag == riot_id:
                            self._active_idx = i
                            self._save()
                            return i
                        # Match label against game name
                        if acct_label and game_name and acct_label == game_name:
                            self._active_idx = i
                            self._save()
                            return i

                    # Also try to auto-populate the Riot ID if we matched by username
                    # but the tagline was empty
                    if riot_id and self._active_idx >= 0:
                        acct = self._accounts[self._active_idx]
                        if not acct.get("tagline"):
                             gn = acct_info.get("game_name", "")
                             tl = acct_info.get("tag_line", "")
                             if gn and tl:
                                 acct["tagline"] = f"{gn}#{tl}"
                                 self._save()

                    # Auto-add previously logged-in account if not found in list
                    if self._active_idx == -1 and riot_id:
                        gn = acct_info.get("game_name", "")
                        tl = acct_info.get("tag_line", "")
                        label = f"{gn}#{tl}" if gn and tl else (gn or "Previously Logged In")
                        
                        exists = False
                        for acct in self._accounts:
                            if acct.get("tagline", "").lower() == label.lower():
                                exists = True
                                break
                        
                        if not exists:
                            self.add_account(
                                label=label,
                                username=riot_login or "Update Username",
                                password="",  # Placeholder empty password
                                tagline=label,
                                region="NA1"
                            )
                            self._active_idx = len(self._accounts) - 1
                            self._save()
                            Logger.info("AccountManager", f"Auto-populated previously logged-in account: {label}")

        except Exception as e:
            Logger.debug("AccountManager", f"Riot Client detection failed: {e}")

        # Method 2: LCU API fallback
        if self.lcu and self.lcu.is_connected:
            try:
                res = self.lcu.request("GET", "/lol-summoner/v1/current-summoner", silent=True)
                if res and res.status_code == 200:
                    data = res.json()
                    game_name = (data.get("gameName") or "").lower()
                    tag_line = (data.get("tagLine") or "").lower()
                    riot_id = f"{game_name}#{tag_line}" if game_name and tag_line else game_name

                    found_idx = -1
                    for i, acct in enumerate(self._accounts):
                        acct_tag = acct.get("tagline", "").lower()
                        acct_label = acct.get("label", "").lower()
                        # Match Riot ID
                        if acct_tag and riot_id and acct_tag == riot_id:
                            found_idx = i
                            break
                        if acct_label and game_name and acct_label == game_name:
                            found_idx = i
                            break

                    if found_idx >= 0:
                        self._active_idx = found_idx
                        self._save()
                        return found_idx
                    elif riot_id:
                        # Discovered LCU account is not in our list — auto-populate
                        gn = data.get("gameName", "")
                        tl = data.get("tagLine", "")
                        label = f"{gn}#{tl}" if gn and tl else (gn or "Previously Logged In")
                        
                        exists = False
                        for acct in self._accounts:
                            if acct.get("tagline", "").lower() == label.lower():
                                exists = True
                                break
                        
                        if not exists:
                            self.add_account(
                                label=label,
                                username="Update Username",
                                password="",
                                tagline=label,
                                region="NA1"
                            )
                            self._active_idx = len(self._accounts) - 1
                            self._save()
                            Logger.info("AccountManager", f"Auto-populated previously logged-in LCU account: {label}")

            except Exception as e:
                Logger.debug("AccountManager", f"LCU detection failed: {e}")

        # Post-detection: Update Wallet if connected
        self._update_wallet()

        return self._active_idx

    def _update_wallet(self):
        """Fetch and cache Blue Essence and RP for the active account."""
        if self._active_idx < 0 or not self.lcu or not self.lcu.is_connected:
            return
            
        try:
            res = self.lcu.request("GET", "/lol-inventory/v1/wallet", silent=True)
            if res and res.status_code == 200:
                wallet_data = res.json()
                rp = wallet_data.get("RP", 0)
                be = wallet_data.get("lol_blue_essence", 0)
                
                with self._lock:
                    self._accounts[self._active_idx]["wallet"] = {"be": be, "rp": rp}
                    self._save()
        except Exception as e:
            Logger.debug("AccountManager", f"Wallet update failed: {e}")

    # ─────────── Helper: Kill Game Processes ───────────
    @staticmethod
    def _kill_game_processes(log_func=None):
        """Kill League Client processes (required before sign-out can work)."""
        killed_any = False
        for proc_name in ["LeagueClient.exe", "LeagueClientUx.exe"]:
            try:
                result = subprocess.run(
                    ["taskkill", "/IM", proc_name, "/F"],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if result.returncode == 0:
                    killed_any = True
                    if log_func:
                        log_func(f"Stopped {proc_name}")
            except Exception:
                pass
        return killed_any

    # ─────────── Login Automation ───────────
    _login_in_progress = False  # Class-level guard against concurrent logins

    def login_account(self, idx: int, log_func=None, completion_func=None):
        """Log into a specific account.

        As requested: dead simple. No killing processes, no reloading.
        Just focus the window, tab, and type the keystrokes.
        """
        if AccountManager._login_in_progress:
            if log_func:
                log_func("Login already in progress...")
            return

        if not (0 <= idx < len(self._accounts)):
            if log_func:
                log_func("Invalid account index.")
            return

        acct = self._accounts[idx]
        username = acct.get("username", "")
        password = self._decrypt(acct.get("password_enc", ""))

        if not username or not password:
            if log_func:
                log_func("Account credentials incomplete.")
            return

        label = acct.get("label", username)

        def _execute():
            AccountManager._login_in_progress = True
            try:
                if log_func:
                    log_func(f"Switching to {label}...")

                # Just run the macro.
                self._keyboard_login(username, password, label, log_func, completion_func, idx)

            except Exception as e:
                Logger.error("AccountManager", f"Login automation failed: {e}")
                if log_func:
                    log_func(f"Login failed: {e}")
                if completion_func:
                    completion_func(False)
            finally:
                AccountManager._login_in_progress = False

        threading.Thread(target=_execute, daemon=True).start()

    # ─────────── Sign Out ───────────

    def sign_out(self, log_func=None, completion_func=None):
        """Sign out the current account. Kills League Client first (required by API)."""
        def _execute():
            try:
                if log_func:
                    log_func("Signing out...")

                if not self.riot_client.is_riot_client_running():
                    if log_func:
                        log_func("Riot Client is not running.")
                    if completion_func:
                        completion_func(False)
                    return

                # Must kill League Client first — API refuses sign-out otherwise
                if log_func:
                    log_func("Closing League Client...")
                self._kill_game_processes(log_func)
                time.sleep(2)

                if not self.riot_client.is_connected:
                    self.riot_client.connect()

                if not self.riot_client.is_connected:
                    if log_func:
                        log_func("Cannot connect to Riot Client.")
                    if completion_func:
                        completion_func(False)
                    return

                success = self.riot_client.sign_out()

                if success:
                    with self._lock:
                        self._active_idx = -1
                        self._save()
                    if log_func:
                        log_func("Signed out successfully!")
                else:
                    if log_func:
                        log_func("Sign out failed. Check the Riot Client.")

                if completion_func:
                    completion_func(success)

            except Exception as e:
                Logger.error("AccountManager", f"Sign out failed: {e}")
                if log_func:
                    log_func(f"Sign out error: {e}")
                if completion_func:
                    completion_func(False)

        threading.Thread(target=_execute, daemon=True).start()

    # ─────────── Keyboard Login (Fallback) ───────────

    def _keyboard_login(self, username, password, label, log_func, completion_func, idx):
        """Fallback: type credentials into the Riot Client login form.

        The Riot Client auto-focuses the username field on launch.
        So the entire login is just: type username → Tab → type password → Enter.
        No mouse clicks, no pixel coordinates, no window position math.
        """
        try:
            import pyautogui
            import ctypes

            user32 = ctypes.windll.user32

            # Wait for the Riot Client window
            hwnd = self._find_riot_client_window(timeout=30)
            if not hwnd:
                if log_func:
                    log_func("Riot Client window not found.")
                if completion_func:
                    completion_func(False)
                return

            # Wait for the login form to fully render
            if log_func:
                log_func("Waiting for login form...")
            time.sleep(0.5)

            # Ensure window is visible and un-minimized
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)

            if log_func:
                log_func(f"Typing credentials for {label}...")

            # Username field is auto-focused on fresh launch.
            # Clear any existing text, type username.
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.write(username, interval=0.03)
            time.sleep(0.2)

            # Tab to password field
            pyautogui.press('tab')
            time.sleep(0.2)

            # Type password
            pyautogui.write(password, interval=0.03)
            time.sleep(0.2)

            # Submit
            pyautogui.press('enter')

            # Wait for auth result via API
            if log_func:
                log_func("Waiting for authentication...")
            self._wait_for_auth_result(idx, label, log_func, completion_func, timeout=15)

        except Exception as e:
            Logger.error("AccountManager", f"Keyboard login failed: {e}")
            if log_func:
                log_func(f"Keyboard login failed: {e}")
            if completion_func:
                completion_func(False)

    # ─────────── Login Helpers ───────────

    def _kill_all_riot_processes(self, log_func=None):
        """Kill ALL Riot/League processes for a clean restart."""
        if log_func:
            log_func("Closing Riot Client...")

        # Kill UI processes first, then the service
        for proc_name in ["LeagueClient.exe", "LeagueClientUx.exe",
                          "RiotClientUx.exe", "Riot Client.exe"]:
            try:
                subprocess.run(
                    ["taskkill", "/IM", proc_name, "/F"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                pass

        time.sleep(1)

        try:
            subprocess.run(
                ["taskkill", "/IM", "RiotClientServices.exe", "/F"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass

        time.sleep(2)

        # Delete stale lockfile
        for lf_path in _RC_LOCKFILE_PATHS:
            try:
                if os.path.exists(lf_path):
                    os.remove(lf_path)
            except Exception:
                pass

    def _wait_for_riot_client_api(self, timeout=30) -> bool:
        """Poll until the Riot Client API is reachable."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.riot_client.connect():
                return True
            time.sleep(1)
        return False

    def _find_riot_client_window(self, timeout=30) -> int:
        """Find the VISIBLE Riot Client window handle."""
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        deadline = time.time() + timeout

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

        while time.time() < deadline:
            found_hwnd = []
            def callback(hwnd, extra):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if buff.value == "Riot Client":
                        found_hwnd.append(hwnd)
                        return False  # Stop enumerating
                return True

            user32.EnumWindows(WNDENUMPROC(callback), 0)
            if found_hwnd:
                return found_hwnd[0]
            time.sleep(0.5)
        return 0

    @staticmethod
    def _get_window_position(hwnd) -> tuple:
        """Return (x, y) of the window's top-left corner."""
        import ctypes

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return rect.left, rect.top

    def _wait_for_auth_result(self, idx, label, log_func, completion_func, timeout=15):
        """Poll the Riot Client API for authentication result after form submission."""
        deadline = time.time() + timeout
        self.riot_client.connect()

        while time.time() < deadline:
            time.sleep(0.5)
            session = self.riot_client.get_session()
            if session:
                err = session.get("error", "")
                if err:
                    if log_func:
                        log_func(f"Login fault: {err}")
                    if completion_func:
                        completion_func(False)
                    return
                if session.get("type", "") == "authenticated":
                    self._record_login_success(idx, label, log_func, completion_func)
                    return

        # Timed out — could still be processing
        if log_func:
            log_func("Login timed out. Check the Riot Client.")
        if completion_func:
            completion_func(False)

    def _record_login_success(self, idx, label, log_func, completion_func):
        """Mark login as successful and update account metadata."""
        with self._lock:
            self._accounts[idx]["last_used"] = datetime.now().isoformat()
            self._active_idx = idx
            self._save()

        if log_func:
            log_func(f"Logged in as {label}!")
        if completion_func:
            completion_func(True)

    # ─────────── Helpers ───────────
    def _launch_riot_client(self):
        """Launch the Riot Client."""
        if self._launch_client_func:
            self._launch_client_func()
            return

        import ctypes
        candidates = [
            r"C:\Riot Games\Riot Client\RiotClientServices.exe",
            r"D:\Riot Games\Riot Client\RiotClientServices.exe",
            r"E:\Riot Games\Riot Client\RiotClientServices.exe",
            os.path.join(
                os.environ.get("USERPROFILE", ""),
                r"Riot Games\Riot Client\RiotClientServices.exe",
            ),
        ]

        # Also check registry
        try:
            import winreg
            for hkey in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
                try:
                    key = winreg.OpenKey(
                        hkey,
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game league_of_legends.live"
                    )
                    val, _ = winreg.QueryValueEx(key, "UninstallString")
                    if val and "RiotClientServices.exe" in val:
                        path = val.split('"')[1] if '"' in val else val.split(' ')[0]
                        if os.path.exists(path):
                            candidates.insert(0, path)
                except Exception:
                    pass
        except Exception:
            pass

        for c in candidates:
            if os.path.exists(c):
                args = "--launch-product=league_of_legends --launch-patchline=live"
                try:
                    ctypes.windll.shell32.ShellExecuteW(
                        None, "open", c, args, None, 1
                    )
                except Exception:
                    subprocess.Popen(
                        [c] + args.split(),
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                return

    def _wait_for_riot_client(self, timeout=30, log_func=None) -> bool:
        """Wait for the Riot Client process to start."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.riot_client.is_riot_client_running():
                time.sleep(2)  # Give it a moment to initialize
                return True
            time.sleep(0.5)
        return False

# Global singleton
_instance = None

def get_account_manager(lcu=None, launch_client_func=None) -> AccountManager:
    global _instance
    if _instance is None:
        _instance = AccountManager(lcu, launch_client_func)
    return _instance
