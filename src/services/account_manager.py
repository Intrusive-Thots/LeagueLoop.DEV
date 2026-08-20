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
from typing import Any, Dict, List, Optional, Tuple

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


class RiotClientAPI:
    """Connects to the local Riot Client (RiotClientServices.exe) API."""

    def __init__(self):
        self.port: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.base_url: Optional[str] = None
        from services.http_session_factory import create_pooled_session
        self.session = create_pooled_session(pool_connections=10, pool_maxsize=10, max_retries=1)
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


class AccountManager:
    """Manages encrypted Riot account credentials and login automation."""

    def __init__(self, lcu=None, launch_client_func=None, state_manager=None):
        self.lcu = lcu
        self._launch_client_func = launch_client_func
        self.state_manager = state_manager
        self.riot_client = RiotClientAPI()
        self._accounts: List[Dict[str, Any]] = []
        self._active_idx: int = -1
        #: Identity the client reports that matches no stored account. Set by
        #: detect_active_account(); the UI offers to add it.
        self._unrecognised: Optional[Dict[str, str]] = None
        self._lock = threading.Lock()
        
        # Migration: Ensure existing accounts have new fields
        self._load()
        self._migrate_accounts()
        self._sync_state()

        # Switching/sign-out sequencing lives in services.accounts so the two
        # operations cannot drift apart. This class keeps ownership of
        # storage, encryption and the account list.
        self._switcher = self._build_switcher()

    def _sync_state(self) -> None:
        """Publish account state to central StateManager."""
        if self.state_manager is not None:
            try:
                active_name = None
                if 0 <= self._active_idx < len(self._accounts):
                    active_name = self._accounts[self._active_idx].get("username")
                all_names = tuple(a.get("username", "") for a in self._accounts)
                self.state_manager.update_account(
                    active_account=active_name,
                    all_accounts=all_names,
                    is_switching=bool(getattr(self, "is_switching", False)),
                )
            except Exception:
                pass

    def _build_switcher(self):
        """Construct the AccountSwitcher, or None if the subsystem is absent."""
        try:
            from core.events import EventBus  # type: ignore
        except Exception:
            EventBus = None  # type: ignore

        try:
            from services.accounts import AccountSwitcher, RiotSession  # type: ignore
        except Exception as exc:  # pragma: no cover - keeps the app usable
            Logger.error("AccountManager", f"Account switcher unavailable: {exc}")
            return None

        return AccountSwitcher(
            session=RiotSession(self.riot_client),
            accounts_provider=lambda: list(self._accounts),
            password_provider=self.get_password,
            on_success=self._mark_active,
            on_signed_out=self._mark_signed_out,
            kill_games=self._kill_game_processes,
            launch_client=self._launch_riot_client,
            bus=EventBus,
        )

    # ─────────── State transitions used by the switcher ───────────
    def _mark_active(self, idx: int) -> None:
        """Record a successful sign-in. Single place that sets the active index."""
        with self._lock:
            if 0 <= idx < len(self._accounts):
                self._accounts[idx]["last_used"] = datetime.now().isoformat()
            self._active_idx = idx
            self._save()
        self._sync_state()

    def _mark_signed_out(self) -> None:
        with self._lock:
            self._active_idx = -1
            self._save()
        self._sync_state()

    def _migrate_accounts(self):
        """
        Ensure all loaded accounts have required fields for new features.

        Only writes when something actually changed - the previous version set
        `dirty = True` unconditionally inside the loop, so it rewrote
        accounts.json on every single startup.
        """
        dirty = False
        defaults = {
            "wallet": lambda: {"be": 0, "rp": 0},
            "region": lambda: "NA1",
            "last_used": lambda: None,
            "is_default": lambda: False,
        }
        for acct in self._accounts:
            for key, make_default in defaults.items():
                if key not in acct:
                    acct[key] = make_default()
                    dirty = True
        if dirty:
            self._save()

    # ─────────── Encryption (DPAPI) ───────────
    @staticmethod
    def _encrypt(plaintext: str) -> str:
        """Encrypt a string using Windows DPAPI, return base64-encoded result."""
        if not plaintext:
            return ""
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
        if not encrypted_b64:
            return ""
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
        """
        Return the stored accounts, in stored order. Pure read.

        This used to sort `self._accounts` in place by `last_used`, recompute
        `_active_idx` and call `_save()` - a *getter* that mutated and wrote
        to disk. Because `last_used` is updated on every successful sign-in,
        the list silently reordered after each login, so an index the UI had
        rendered a moment earlier could point at a different account by the
        time the user clicked it. That is how you end up switching into the
        wrong account.

        Indices returned here are stable and are what `switch_to()`,
        `get_password()` and `delete_account()` expect. For most-recent-first
        display order, use `get_accounts_display()`, which keeps the real
        index alongside each account.
        """
        with self._lock:
            return [dict(a) for a in self._accounts]

    def get_accounts_display(self) -> List[Tuple[int, Dict[str, Any]]]:
        """
        (index, account) pairs, most recently used first.

        Lets a UI show recency ordering while still carrying the stable index
        that every mutating call needs.
        """
        def parse_date(value):
            if not value:
                return datetime.min
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return datetime.min

        with self._lock:
            pairs = [(i, dict(a)) for i, a in enumerate(self._accounts)]

        pairs.sort(key=lambda pair: parse_date(pair[1].get("last_used")), reverse=True)
        return pairs

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

    def has_valid_credentials(self, idx: int) -> bool:
        """Return True if account has a username and a password that decrypts cleanly."""
        if not (0 <= idx < len(self._accounts)):
            return False
        acct = self._accounts[idx]
        if not acct.get("username"):
            return False
        enc = acct.get("password_enc", "")
        if not enc:
            return False
        pwd = self._decrypt(enc)
        return bool(pwd)

    # ─────────── Active Account Detection ───────────
    def _read_identity(self):
        """
        Ask the Riot Client who is signed in, falling back to the LCU.

        Returns a `ClientIdentity`. The Riot Client is preferred because it is
        the only source that knows the *login* username; the LCU only knows
        the in-game name, so an LCU-derived identity can never match on
        username.
        """
        from services.accounts.identity import (
            ClientIdentity,
            from_lcu_summoner,
            from_riot_userinfo,
        )

        try:
            if self.riot_client.connect():
                identity = from_riot_userinfo(self.riot_client.get_current_user())
                if not identity.is_empty:
                    return identity
        except Exception as e:
            Logger.debug("AccountManager", f"Riot Client detection failed: {e}")

        if self.lcu and getattr(self.lcu, "is_connected", False):
            try:
                res = self.lcu.request(
                    "GET", "/lol-summoner/v1/current-summoner", silent=True
                )
                if res is not None and res.status_code == 200:
                    return from_lcu_summoner(res.json())
            except Exception as e:
                Logger.debug("AccountManager", f"LCU detection failed: {e}")

        return ClientIdentity()

    def get_unrecognised_identity(self) -> Optional[Dict[str, str]]:
        """
        The signed-in identity that matched no stored account, or None.

        This replaces the old behaviour of silently calling `add_account()`
        with an empty password and the username "Update Username". That
        created rows which could never sign in, from a background thread, with
        no way for the user to know where they came from. Surfacing the
        identity instead lets the UI offer to add it *with* a password.
        """
        with self._lock:
            return dict(self._unrecognised) if self._unrecognised else None

    def detect_active_account(self) -> int:
        """
        Detect which stored account is currently signed in.

        Returns the account index, or -1. Unlike the previous version this
        only ever *reads* the client: it does not create accounts, and it
        takes the lock before touching shared state, because it runs on a
        background thread alongside the switcher.
        """
        from services.accounts.identity import match_account, missing_tagline_update

        identity = self._read_identity()

        if identity.is_empty:
            with self._lock:
                self._unrecognised = None
            self._update_wallet()
            return self._active_idx

        with self._lock:
            accounts = list(self._accounts)
            match = match_account(identity, accounts)

            dirty = False
            if match.confident:
                if self._active_idx != match.index:
                    self._active_idx = match.index
                    dirty = True
                self._unrecognised = None

                fill = missing_tagline_update(identity, self._accounts[match.index])
                if fill:
                    self._accounts[match.index]["tagline"] = fill
                    dirty = True

            elif match.found:
                # A label that happens to equal an in-game name is a
                # coincidence, not an identification. Report it, do not act
                # on it.
                Logger.debug(
                    "AccountManager",
                    "Ignoring low-confidence account match for "
                    f"{identity.display_name()} (matched a label only)",
                )
                self._unrecognised = self._identity_dict(identity)

            else:
                self._unrecognised = self._identity_dict(identity)
                Logger.info(
                    "AccountManager",
                    f"Signed-in account {identity.display_name()} is not stored",
                )

            if dirty:
                self._save()
            active = self._active_idx

        self._update_wallet()
        return active

    @staticmethod
    def _identity_dict(identity) -> Dict[str, str]:
        return {
            "username": identity.login_name,
            "tagline": identity.riot_id,
            "display_name": identity.display_name(),
        }

    def _update_wallet(self):
        """
        Cache Blue Essence and RP for the active account.

        The index is re-read *inside* the lock: this runs on a background
        thread, and the previous version checked `_active_idx` outside the
        lock and then indexed with it, which raises IndexError if an account
        was removed in between. It also wrote accounts.json on every call;
        now it only writes when the numbers actually changed.
        """
        if not self.lcu or not getattr(self.lcu, "is_connected", False):
            return

        try:
            res = self.lcu.request("GET", "/lol-inventory/v1/wallet", silent=True)
            if not (res is not None and res.status_code == 200):
                return
            wallet_data = res.json()
            wallet = {
                "be": wallet_data.get("lol_blue_essence", 0),
                "rp": wallet_data.get("RP", 0),
            }
        except Exception as e:
            Logger.debug("AccountManager", f"Wallet update failed: {e}")
            return

        with self._lock:
            idx = self._active_idx
            if not (0 <= idx < len(self._accounts)):
                return
            if self._accounts[idx].get("wallet") == wallet:
                return
            self._accounts[idx]["wallet"] = wallet
            self._save()

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

    # ─────────── Account switching ───────────

    def switch_to(self, idx: int, launch_league: bool = True):
        """
        Switch to an account and return a typed SwitchResult. Blocking.

        Prefer this over `login_account` in new code: it tells you *why*
        something failed (bad credentials vs 2FA vs client not running)
        instead of just False.
        """
        if self._switcher is None:
            from services.accounts.results import SwitchOutcome, SwitchResult

            return SwitchResult(SwitchOutcome.ERROR, detail="switcher unavailable")
        return self._switcher.switch_to(idx, launch_league=launch_league)

    @property
    def is_switching(self) -> bool:
        return bool(self._switcher and self._switcher.busy)

    def login_account(self, idx: int, log_func=None, completion_func=None,
                      launch_league: bool = True):
        """
        Log into a specific account, on a background thread.

        Rewritten: this now performs the full, consistent sequence - reach the
        client, sign the current account out, authenticate through the Riot
        Client API, verify, then optionally launch League.

        Previously it typed the username and password as keystrokes into
        whatever window held focus and never signed out first, so switching
        only worked from an already-signed-out state.

        `log_func` / `completion_func` are kept so existing callers keep
        working; new code should use `switch_to()` or listen for the
        account_switch_* events.
        """
        if self._switcher is None:
            if log_func:
                log_func("Account switching is unavailable.")
            if completion_func:
                completion_func(False)
            return

        def _execute():
            handle = None
            if log_func:
                handle = self._subscribe_progress(log_func)
            try:
                result = self._switcher.switch_to(idx, launch_league=launch_league)
                if log_func:
                    log_func(result.message)
                if completion_func:
                    completion_func(result.ok)
            finally:
                if handle is not None:
                    try:
                        handle.dispose()
                    except Exception:
                        pass

        threading.Thread(target=_execute, daemon=True).start()

    def sign_out(self, log_func=None, completion_func=None):
        """
        Sign out the current account, on a background thread.

        Shares the switcher's lock and sequence, so a sign-out can no longer
        run in the middle of a sign-in.
        """
        if self._switcher is None:
            if log_func:
                log_func("Account switching is unavailable.")
            if completion_func:
                completion_func(False)
            return

        def _execute():
            handle = None
            if log_func:
                handle = self._subscribe_progress(log_func)
            try:
                result = self._switcher.sign_out()
                if log_func:
                    log_func(result.message)
                if completion_func:
                    completion_func(result.ok)
            finally:
                if handle is not None:
                    try:
                        handle.dispose()
                    except Exception:
                        pass

        threading.Thread(target=_execute, daemon=True).start()

    @staticmethod
    def _subscribe_progress(log_func):
        """Bridge switcher progress events to a legacy log callback."""
        try:
            from core.events import EventBus  # type: ignore
            from services.accounts.results import EVENT_SWITCH_PROGRESS  # type: ignore
        except Exception:
            return None

        def _on_progress(progress=None, *_a, **_kw):
            message = getattr(progress, "message", None)
            if message:
                try:
                    log_func(message)
                except Exception:
                    pass

        try:
            return EventBus.on(EVENT_SWITCH_PROGRESS, _on_progress)
        except Exception:
            return None

    # ─────────── Removed: keyboard login ───────────
    #
    # `_keyboard_login()` and its helpers (`_find_riot_client_window`,
    # `_wait_for_auth_result`, `_record_login_success`) typed the username and
    # password into the Riot Client with `pyautogui.write()`. That sends the
    # password as keystrokes to whatever window holds focus at that instant -
    # a notification, the client repainting, or another app stealing focus
    # mid-type means the password lands somewhere else entirely.
    #
    # It was already off the login path; sign-in goes through the local client
    # API in `services.accounts.RiotSession.sign_in`. Keeping a dormant copy
    # meant the credential-leak path still existed in the binary and could be
    # re-enabled by a future "fallback" change, so it is gone rather than
    # deprecated. Git history has it if it is ever genuinely needed.

    # ─────────── Helpers ───────────
    def _launch_riot_client(self, launch_league: bool = True):
        """Launch the Riot Client or League of Legends Client."""
        if self._launch_client_func and launch_league:
            self._launch_client_func()
            return

        import ctypes
        primary_target = r"C:\Riot Games\Riot Client\RiotClientServices.exe"
        candidates = [primary_target] if os.path.exists(primary_target) else []

        # Additional candidates & registry lookups as fallback
        fallback_candidates = [
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
                        if os.path.exists(path) and path not in candidates:
                            fallback_candidates.append(path)
                except Exception:
                    pass
        except Exception:
            pass

        for fc in fallback_candidates:
            if fc not in candidates:
                candidates.append(fc)

        args = "--launch-product=league_of_legends --launch-patchline=live" if launch_league else ""
        for c in candidates:
            if os.path.exists(c):
                try:
                    ctypes.windll.shell32.ShellExecuteW(
                        None, "open", c, args, None, 1
                    )
                except Exception:
                    cmd = [c] + args.split() if args else [c]
                    subprocess.Popen(
                        cmd,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                return
