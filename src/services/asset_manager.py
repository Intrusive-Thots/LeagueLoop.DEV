"""
Manages external assets, champions, and configurations.
"""
from utils.logger import Logger
import json
import os
import threading
import queue
import time
from typing import Any, Dict, Optional
from collections import OrderedDict

import requests
from PIL import Image

class HeadlessImage:
    """Mock class that mimics ctk.CTkImage for PySide6 compatibility without Tkinter."""
    def __init__(self, pil_img, size=None):
        self._image = pil_img
        self.size = size or pil_img.size

from utils.path_utils import get_asset_path, get_data_dir

# Directories
USER_DATA_DIR = get_data_dir()
USER_CONFIG_FILE = os.path.join(USER_DATA_DIR, "config.json")
BUNDLED_CONFIG_FILE = get_asset_path("config.json")

CACHE_DIR = os.path.join(USER_DATA_DIR, "cache")
CHAMPIONS_CACHE_DIR = os.path.join(CACHE_DIR, "champions")
ITEMS_CACHE_DIR = os.path.join(CACHE_DIR, "items")
SKINS_CACHE_DIR = os.path.join(CACHE_DIR, "skins")
METADATA_CACHE_DIR = os.path.join(CACHE_DIR, "metadata")
BUNDLED_ASSETS_DIR = get_asset_path("assets")

# Ensure user directories exist
for sub_dir in [CACHE_DIR, CHAMPIONS_CACHE_DIR, ITEMS_CACHE_DIR, SKINS_CACHE_DIR, METADATA_CACHE_DIR]:
    try:
        os.makedirs(sub_dir, exist_ok=True)
    except OSError:
        pass

DEFAULT_CONFIG = {
    "auto_accept": False,
    "auto_requeue": False,
    "auto_pick": "",  # Legacy/Global Fallback
    "auto_pick_backup": "",
    "auto_ban": "",
    "custom_status": "🎮 LeagueLoop ⚙️ https://github.com/Intrusive-Thots/LeagueLoop-Installer",
    "auto_aram_swap": False,
    "auto_set_roles": False,
    "auto_hover": False,
    "auto_lock_in": False,
    "auto_random_skin": True,
    "accept_delay": 2.0,
    "polling_rate_champ_select": 0.5,  # Default to Fast for CS
    # Role-Based Picks (3 slots per role)
    "pick_TOP_1": "",
    "pick_TOP_2": "",
    "pick_TOP_3": "",
    "pick_JUNGLE_1": "",
    "pick_JUNGLE_2": "",
    "pick_JUNGLE_3": "",
    "pick_MIDDLE_1": "",
    "pick_MIDDLE_2": "",
    "pick_MIDDLE_3": "",
    "pick_BOTTOM_1": "",
    "pick_BOTTOM_2": "",
    "pick_BOTTOM_3": "",
    "pick_UTILITY_1": "",
    "pick_UTILITY_2": "",
    "pick_UTILITY_3": "",
    # Role-Based Bans
    "ban_TOP_1": "",
    "ban_TOP_2": "",
    "ban_TOP_3": "",
    "ban_JUNGLE_1": "",
    "ban_JUNGLE_2": "",
    "ban_JUNGLE_3": "",
    "ban_MIDDLE_1": "",
    "ban_MIDDLE_2": "",
    "ban_MIDDLE_3": "",
    "ban_BOTTOM_1": "",
    "ban_BOTTOM_2": "",
    "ban_BOTTOM_3": "",
    "ban_UTILITY_1": "",
    "ban_UTILITY_2": "",
    "ban_UTILITY_3": "",
    "always_on_top": True,
    "poro_snacks": 0,
    "stealth_mode": False,
    "hotkey_launch_client": "ctrl+shift+l",
    "hotkey_toggle_automation": "ctrl+shift+a",
    "hotkey_find_match": "ctrl+shift+f",
    "hotkey_compact_mode": "ctrl+shift+m",
    "priority_picker": {
        "enabled": True,
        "list": [
            "Nautilus",
            "Xerath",
            "Nunu & Willump",
            "Master Yi",
            "Veigar",
            "Lux",
            "Heimerdinger",
            "Nidalee",
            "Pyke",
            "Jhin"
        ]
    },
    "arena_pairs": [],
    "arena_auto_lock": False,
    "arena_synergy_enabled": True,
    "run_in_tray": True,
    "discord_rpc_enabled": True,
    "skip_stats_enabled": True,
    "auto_runes_enabled": True,
    "auto_runes": True,
    "aram_auto_add_played": False,
    "league_client_path": "",
    "riot_client_path": ""
}




DDRAGON_VER = "14.1.1"

_cached_ddragon_ver = None


class ConfigManager:
    """Manages application configuration."""

    def __init__(self):
        """Initializes the ConfigManager."""
        self.cfg = DEFAULT_CONFIG.copy()

        # 1. Load bundled template first (transfers dev configurations to users)
        if os.path.exists(BUNDLED_CONFIG_FILE):
            try:
                with open(BUNDLED_CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.cfg.update(json.load(f))
            except Exception as e:
                Logger.debug("Assets", f"Bundled config load failed: {e}")

        # 2. Override with the user's local runtime config
        if os.path.exists(USER_CONFIG_FILE):
            try:
                with open(USER_CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.cfg.update(json.load(f))
            except Exception as e:
                Logger.error("asset_manager.py", f"Handled exception: {type(e).__name__}: {e}")
        else:
            self.save()

        # 3. Restore any persisted settings from SQLite Database
        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager.get_instance()
            for k, val_str in db.get_all_settings().items():
                try:
                    self.cfg[k] = json.loads(val_str)
                except Exception:
                    self.cfg[k] = val_str
        except Exception:
            pass

        # 4. Auto-detect client installation paths on initial setup
        try:
            from utils.client_detector import resolve_installation_paths
            l_path, r_path = resolve_installation_paths()
            if l_path and not self.cfg.get("league_client_path"):
                self.cfg["league_client_path"] = os.path.join(l_path, "LeagueClient.exe")
            if r_path and not self.cfg.get("riot_client_path"):
                self.cfg["riot_client_path"] = os.path.join(r_path, "RiotClientServices.exe")
        except Exception as e:
            Logger.debug("ConfigManager", f"Client path detection error: {e}")

    def get(self, key, default=None):
        """Get a configuration value."""
        return self.cfg.get(key, default)

    def set(self, key, val, save=True):
        """Set a configuration value and optionally save to file."""
        self.cfg[key] = val
        if save:
            self.save()

    def set_batch(self, updates: dict, save=True):
        """Set multiple configuration values and optionally save to file."""
        self.cfg.update(updates)
        if save:
            self.save()

    def save(self):
        """Save configuration securely to AppData config.json and SQLite database."""
        try:
            target_dir = os.path.dirname(USER_CONFIG_FILE)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            tmp_path = USER_CONFIG_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=4)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp_path, USER_CONFIG_FILE)
        except Exception as e:
            Logger.error("asset_manager.py", f"Failed saving config: {e}")

        # Sync to SQLite Database
        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager.get_instance()
            for k, v in self.cfg.items():
                db.set_setting(k, json.dumps(v))
        except Exception:
            pass




class AssetManager:
    """Manages application assets (images, data)."""

    def __init__(self, log_func=None, cache_dir=None):
        """Initializes the AssetManager."""
        self._log_func = log_func
        self.cache_dir = cache_dir or CACHE_DIR
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

        self.champ_data: Dict[str, Any] = {}
        self.id_to_key: Dict[int, str] = {}  # ID (int) -> Key/DDragonID (str)
        self.id_to_tags: Dict[int, list] = {}  # ID (int) -> List[Tags]
        self.name_to_id: Dict[str, int] = {}  # Name/Key (lower) -> ID (int)
        self.champ_roles: Dict[int, list] = {}  # ID -> List[Positions]
        self.icons: OrderedDict[str, HeadlessImage] = OrderedDict()

        self._pending_downloads = set()
        self._lock = threading.Lock()

        # Bolt: Use a Queue + Daemon Threads to prevent thread explosion during high load
        # (e.g., skin selector) while ensuring clean app exit.
        self._download_queue = queue.Queue()
        from core.constants import DOWNLOAD_WORKER_COUNT
        for _ in range(DOWNLOAD_WORKER_COUNT):
            threading.Thread(target=self._download_worker, daemon=True).start()

        self.session = requests.Session()

        # Initialize version from cache if available, otherwise use default
        global _cached_ddragon_ver
        if _cached_ddragon_ver:
            self.ddragon_ver = _cached_ddragon_ver
        else:
            self.ddragon_ver = DDRAGON_VER
            v_path = os.path.join(CACHE_DIR, "version.txt")
            if os.path.exists(v_path):
                try:
                    with open(v_path, "r", encoding="utf-8") as f:
                        self.ddragon_ver = f.read().strip()
                        _cached_ddragon_ver = self.ddragon_ver
                except Exception as e:
                    Logger.error("asset_manager.py", f"Handled exception: {type(e).__name__}: {e}")

    def _download_worker(self):
        """Worker thread for background downloads."""
        while True:
            func = self._download_queue.get()
            try:
                func()
            except Exception as e:  # pylint: disable=broad-exception-caught
                Logger.error("asset_manager.py", f"Handled exception: {type(e).__name__}: {e}")
            finally:
                self._download_queue.task_done()

    def log(self, msg):
        """Safe logging method that handles None log function."""
        if self._log_func:
            self._log_func(msg)
        else:
            print(f"[Assets] {msg}")

    def start_loading(self):
        """Start loading assets in a background thread."""
        threading.Thread(target=self._load_all, daemon=True).start()

    def _fetch_latest_version(self):
        """Fetches the latest Data Dragon version."""
        try:
            url = "https://ddragon.leagueoflegends.com/api/versions.json"
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                versions = response.json()
                if versions and isinstance(versions, list):
                    latest = versions[0]
                    if latest != self.ddragon_ver:
                        global _cached_ddragon_ver
                        self.log(f"Updated Data Dragon version to {latest}")
                        self.ddragon_ver = latest
                        _cached_ddragon_ver = latest
                        v_path = os.path.join(CACHE_DIR, "version.txt")
                        with open(v_path, "w", encoding="utf-8") as f:
                            f.write(self.ddragon_ver)

                        # Invalidate stale data caches so they re-download
                        for filename in ("champion.json", "item.json", "summoner.json"):
                            path = os.path.join(CACHE_DIR, filename)
                            if os.path.exists(path):
                                try:
                                    os.remove(path)
                                except Exception as e:
                                    Logger.error("asset_manager.py", f"Handled exception: {type(e).__name__}: {e}")
        except Exception as e:
            self.log(f"Failed to fetch latest version: {e}")

    def _load_all(self):
        self._fetch_latest_version()
        self.log("Downloading Data Assets...")

        # Preload Profile Background
        try:
            cfg = ConfigManager()
            bg_id = cfg.get("profile_bg_id")
            if bg_id:
                self.log(f"Preloading background {bg_id}...")
                self.get_splash_art(int(bg_id), width=1100, opacity=0.5)
        except Exception as e:  # pylint: disable=broad-exception-caught
            Logger.error("asset_manager.py", f"Handled exception: {type(e).__name__}: {e}")

        self._load_champion_data()
        self._load_meraki_data()
        self.preload_champion_icons()
        self.log("Assets Loaded.")

    def _load_champion_data(self):
        path = os.path.join(CACHE_DIR, "champion.json")
        try:
            if not os.path.exists(path):
                url = f"https://ddragon.leagueoflegends.com/cdn/{self.ddragon_ver}/data/en_US/champion.json"
                data = self.session.get(url, timeout=10).json()
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f)

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.champ_data = data["data"]

            # Populate Lookup Maps
            self.id_to_key = {}
            self.id_to_tags = {}
            self.name_to_id = {}
            for key_str, info in self.champ_data.items():
                try:
                    cid = int(info["key"])
                    name = info["name"]

                    self.id_to_key[cid] = key_str
                    self.id_to_tags[cid] = info.get("tags", [])

                    # Map both DDragon Key (e.g. "MonkeyKing") and Name (e.g. "Wukong")
                    self.name_to_id[key_str.lower()] = cid
                    self.name_to_id[name.lower()] = cid
                except (ValueError, KeyError):
                    continue

        except Exception as e:  # pylint: disable=broad-exception-caught
            Logger.error("asset_manager.py", f"Handled exception: {type(e).__name__}: {e}")
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError as e:
                Logger.warning("asset_manager.py", f"Failed to remove file {path}: {e}")

    def _load_meraki_data(self):
        """Load detailed champion data (including roles) from Meraki Analytics."""
        path = os.path.join(CACHE_DIR, "meraki_champions.json")
        try:
            # Download if missing or stale (simple check: if we just updated ddragon, update this too)
            if not os.path.exists(path):
                url = "https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions.json"
                r = self.session.get(url, timeout=15)
                if r.status_code == 200:
                    try:
                        data_to_write = r.json()
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(data_to_write, f)
                    except json.JSONDecodeError as e:
                        Logger.error("asset_manager.py", f"Failed to parse Meraki download: {e}")
                        return

            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                     try:
                         data = json.load(f)
                     except json.JSONDecodeError as e:
                         Logger.error("asset_manager.py", f"Corrupted Meraki cache, deleting: {e}")
                         os.remove(path)
                         return
                     # Parse roles: ID -> [Positions]
                     self.champ_roles = {}
                     for _, info in data.items():
                         try:
                             cid = info.get("id", 0)
                             positions = info.get("positions", [])
                             if cid and positions:
                                 # Normalize "SUPPORT" -> "UTILITY" to match internal convention
                                 clean_pos = [
                                     "UTILITY" if p == "SUPPORT" else p 
                                     for p in positions
                                 ]
                                 self.champ_roles[int(cid)] = clean_pos
                         except Exception as e:
                             Logger.error("asset_manager.py", f"Handled exception: {e}")
                             continue
                self.log(f"Loaded Meraki role data for {len(self.champ_roles)} champions.")

        except Exception as e:
            Logger.error("asset_manager.py", f"Failed to load Meraki data: {type(e).__name__}: {e}")
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError as e:
                Logger.warning("asset_manager.py", f"Failed to remove file {path}: {e}")

    def get_champ_name(self, champ_id: int) -> str:
        """Get champion name by ID."""
        # ⚡ Bolt: Fast-path EAFP optimization to prevent eager string allocation.
        # Previously, `.get(champ_id, str(champ_id))` forced Python to allocate `str(champ_id)`
        # on every single lookup. By using try/except, we defer the expensive string conversion
        # entirely to the rare cache miss path.
        try:
            return self.id_to_key[champ_id]
        except KeyError:
            return str(champ_id)

    def _simple_download(self, url, path):
        try:
            # Enable SSL verification for security
            r = self.session.get(url, timeout=10)
            if r.status_code == 200:
                tmp_path = f"{path}.tmp"
                with open(tmp_path, "wb") as f:
                    f.write(r.content)
                # Atomic replace guarantees os.path.exists(path) is only true
                # when the file is 100% complete and valid for Image.open to read.
                os.replace(tmp_path, path)
            else:
                Logger.warning("asset_manager.py", f"Failed {url} -> {r.status_code}")
        except Exception as e:  # pylint: disable=broad-exception-caught
            Logger.error("asset_manager.py", f"Exception {url} -> {e}")

    def _start_download(self, url, path):
        """Helper to start a download if not already in progress."""
        with self._lock:
            if path in self._pending_downloads:
                return
            self._pending_downloads.add(path)

        def _target():
            try:
                self._simple_download(url, path)
            finally:
                with self._lock:
                    if path in self._pending_downloads:
                        self._pending_downloads.remove(path)
        self._download_queue.put(_target)

    def _download_and_cache_image(self, url, path, cache_key, size=None, opacity=1.0):
        if cache_key in self.icons:
            # LRU Cache Hit: move to end
            img = self.icons.pop(cache_key)
            self.icons[cache_key] = img
            return img

        # Check for pre-processed image on disk
        # We replace spaces and invalid characters in cache_key to be safe
        safe_key = cache_key.replace(" ", "_").replace(":", "").replace("/", "_")
        processed_fname = f"processed_{safe_key}.png"
        processed_path = os.path.join(CACHE_DIR, processed_fname)

        if os.path.exists(processed_path):
            try:
                pil_img = Image.open(processed_path).convert("RGBA")
                # CTkImage size requires integer tuple, fallback to original if size contains None
                disp_size = size if size and size[1] is not None else pil_img.size
                img = HeadlessImage(pil_img, size=disp_size)
                self.icons[cache_key] = img
                if len(self.icons) > 300:
                    self.icons.popitem(last=False)
                return img
            except Exception as e:
                Logger.debug("Assets", f"Cached icon corrupt, regenerating: {e}")

        if os.path.exists(path):
            try:
                pil_img = Image.open(path).convert("RGBA")

                # Resize
                if size and pil_img.size[:2] != size[:2]:
                    # If only width is provided or aspect ratio should be kept, handle it:
                    if size[1] is None:
                        aspect = pil_img.height / pil_img.width
                        height = int(size[0] * aspect)
                        size = (size[0], height)
                    pil_img = pil_img.resize(size, Image.Resampling.BICUBIC)
                else:
                    if size and size[1] is None:
                        aspect = pil_img.height / pil_img.width
                        size = (size[0], int(size[0] * aspect))

                # Opacity
                if opacity < 1.0:
                    alpha = pil_img.split()[3]
                    lut = [int(p * opacity) for p in range(256)]
                    alpha = alpha.point(lut)
                    pil_img.putalpha(alpha)

                # Save processed version to disk for future fast-loads
                try:
                    pil_img.save(processed_path, "PNG")
                except Exception as e:
                    Logger.debug("Assets", f"Failed to cache processed icon: {e}")

                img_size = size if size and size[1] is not None else pil_img.size
                img = HeadlessImage(pil_img, size=img_size)
                self.icons[cache_key] = img
                with self._lock:
                    if len(self.icons) > 300:
                        self.icons.popitem(last=False)
                return img
            except Exception as e:
                Logger.error("asset_manager.py", f"Image load error: {e}")
                return None

        self._start_download(url, path)
        return None

    def get_icon(self, type_, key, size=(40, 40)) -> Optional[HeadlessImage]:
        """Synchronously get an icon if cached on disk, otherwise trigger a download and return None."""
        cache_key = f"{type_}_{key}_{size[0]}x{size[1]}"
        fname = ""
        url = ""

        if type_ == "champion":
            # DDragon uses champion name keys (e.g. "Yuumi"), not numeric IDs (e.g. "350")
            # or display names with spaces (e.g. "Twisted Fate" -> "TwistedFate")
            resolved_key = key
            if key.isdigit() and hasattr(self, "id_to_key"):
                resolved_key = self.id_to_key.get(int(key), key)
            elif hasattr(self, "name_to_id") and hasattr(self, "id_to_key"):
                cid = self.name_to_id.get(key.lower())
                if cid is not None:
                    resolved_key = self.id_to_key.get(cid, key)
            fname = f"champion_{resolved_key}.png"
            url = f"https://ddragon.leagueoflegends.com/cdn/{self.ddragon_ver}/img/champion/{resolved_key}.png"
        elif type_ == "item":
            fname = f"item_{key}.png"
            url = f"https://ddragon.leagueoflegends.com/cdn/{self.ddragon_ver}/img/item/{key}.png"
        elif type_ == "profileicon":
            fname = f"profileicon_{key}.png"
            url = f"https://ddragon.leagueoflegends.com/cdn/{self.ddragon_ver}/img/profileicon/{key}.png"
        else:
            return None

        path = os.path.join(CACHE_DIR, fname)
        return self._download_and_cache_image(url, path, cache_key, size=size)

    def preload_champion_icons(self, size=(48, 48)):
        """Background preloader for all champion icons to maximize UI responsiveness."""
        if not self.id_to_key:
            return

        def _preload_job():
            count = 0
            for key_str in list(self.id_to_key.values()):
                fname = f"champion_{key_str}.png"
                path = os.path.join(CACHE_DIR, fname)
                if not os.path.exists(path):
                    url = f"https://ddragon.leagueoflegends.com/cdn/{self.ddragon_ver}/img/champion/{key_str}.png"
                    self._start_download(url, path)
                    count += 1
            if count > 0:
                self.log(f"Queued {count} champion icons for background caching.")

        threading.Thread(target=_preload_job, daemon=True).start()

    def get_icon_async(self, type_, key, callback, size=(40, 40), widget=None):
        """Helper to get an icon asynchronously and call the callback when ready."""
        img = self.get_icon(type_, key, size=size)
        if img:
            callback(img)
            return

        if widget is not None:
            def _poll(attempts=50):
                if hasattr(widget, "winfo_exists"):
                    try:
                        if not widget.winfo_exists():
                            return
                    except Exception:
                        return
                elif hasattr(widget, "isWidgetType"):
                    try:
                        if not widget.isVisible() and attempts < 45:
                            pass
                    except Exception:
                        return

                poll_img = self.get_icon(type_, key, size=size)
                if poll_img:
                    callback(poll_img)
                    return

                if attempts > 0:
                    if hasattr(widget, "after"):
                        widget.after(100, lambda: _poll(attempts - 1))
                    else:
                        def _qt_poll():
                            _poll(attempts - 1)
                        try:
                            from PySide6.QtCore import QTimer
                            QTimer.singleShot(100, _qt_poll)
                        except Exception:
                            threading.Thread(target=lambda: (time.sleep(0.1), _poll(attempts - 1)), daemon=True).start()

            if hasattr(widget, "after"):
                widget.after(0, _poll)
            else:
                _poll()
        else:
            def _wait():
                for _ in range(50):  # Wait up to 5 seconds
                    poll_img = self.get_icon(type_, key, size=size)
                    if poll_img:
                        callback(poll_img)
                        return
                    time.sleep(0.1)
            threading.Thread(target=_wait, daemon=True).start()

    def get_splash_art(
        self, skin_id: int, width=1280, opacity=1.0
    ) -> Optional[HeadlessImage]:
        """Get a CTkImage for the specified skin splash art."""
        cache_key = f"splash_{skin_id}_{width}_{opacity}"

        if cache_key in self.icons:
            img = self.icons.pop(cache_key)
            self.icons[cache_key] = img
            return img

        try:
            champ_id = skin_id // 1000
            skin_num = skin_id % 1000
            ddragon_id = self.get_champ_name(champ_id)
            if not ddragon_id or ddragon_id == str(champ_id):
                return None
        except Exception as e:
            Logger.error("asset_manager.py", f"Handled exception: {type(e).__name__}: {e}")
            return None

        fname = f"splash_{ddragon_id}_{skin_num}.jpg"
        path = os.path.join(CACHE_DIR, fname)
        url = f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{ddragon_id}_{skin_num}.jpg"

        return self._download_and_cache_image(url, path, cache_key, size=(width, None), opacity=opacity)

    def get_champion_icon_path(self, champion_key: str) -> str:
        """Return absolute path to cached champion icon image file."""
        resolved = champion_key
        if hasattr(self, "id_to_key") and champion_key.isdigit():
            resolved = self.id_to_key.get(int(champion_key), champion_key)
        elif hasattr(self, "name_to_id") and hasattr(self, "id_to_key"):
            cid = self.name_to_id.get(champion_key.lower())
            if cid is not None:
                resolved = self.id_to_key.get(cid, champion_key)
        fname = f"champion_{resolved}.png"
        return os.path.join(CACHE_DIR, fname)

    def get_default_icon_path(self) -> str:
        """Return default fallback icon path."""
        return os.path.join(CACHE_DIR, "default.png")

    def get_known_champions(self) -> dict:
        """Returns a dict mapping lowercase key/name to actual DDragon champion key string."""
        known = {}
        if hasattr(self, "champ_data") and self.champ_data:
            for key_str, info in self.champ_data.items():
                known[key_str.lower()] = key_str
                name = info.get("name", "")
                if name:
                    known[name.lower()] = key_str
        return known

