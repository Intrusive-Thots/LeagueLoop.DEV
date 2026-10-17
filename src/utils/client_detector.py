"""
Client Detector Utility
───────────────────────
Provides unified, cached process detection and installation path resolution
for both the Riot Client and the League of Legends Client.
"""
import json
import os
import re
import time
import psutil
from typing import Any, Dict, List, Optional, Tuple
from utils.logger import Logger

# Precompiled credential regexes
_PORT_REGEX = re.compile(r"--app-port=([0-9]+)")
_TOKEN_REGEX = re.compile(r"--remoting-auth-token=([\w-]+)")

# Scan cache configuration
_CACHE_TTL = 2.0  # 2 seconds cache lifetime
_last_scan_time = 0.0
_cached_results: Dict[str, Dict] = {
    "league": {"port": None, "token": None, "connected": False, "pid": None},
    "riot": {"port": None, "token": None, "connected": False, "pid": None}
}

# Resolved installation paths
_league_install_path: Optional[str] = None
_riot_install_path: Optional[str] = None
_paths_resolved = False


def _select_best_league_path(assoc: Dict[str, Any], user_profile: str) -> Optional[str]:
    """
    Selects the best League install path from associated_client map.
    Prefers paths that exist on disk and belong to the current user.
    """
    best_path: Optional[str] = None
    best_is_user = False
    for game_path in assoc.keys():
        if "league of legends" not in game_path.lower():
            continue
        norm = os.path.normpath(game_path)
        exists = os.path.isdir(norm)
        is_user = bool(user_profile and game_path.replace("\\", "/").rstrip("/").lower().startswith(user_profile))
        if best_path is None or (exists and (not best_is_user and is_user)):
            best_path = norm
            best_is_user = is_user
    return best_path


def resolve_installation_paths() -> Tuple[Optional[str], Optional[str]]:
    """
    Parses RiotClientInstalls.json to resolve installation directories.
    Returns: (league_install_path, riot_install_path)
    """
    global _league_install_path, _riot_install_path, _paths_resolved
    if _paths_resolved:
        return _league_install_path, _riot_install_path

    paths_to_try = [
        os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "Riot Games", "RiotClientInstalls.json"),
        os.path.join(os.environ.get("ALLUSERSPROFILE", "C:\\ProgramData"), "Riot Games", "RiotClientInstalls.json"),
    ]

    for p in paths_to_try:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)

                rc_path = data.get("rc_default") or data.get("rc_live")
                if rc_path:
                    rc_path = os.path.normpath(rc_path)
                    _riot_install_path = os.path.dirname(rc_path)
                    Logger.debug("Detector", f"Resolved Riot Client path: {_riot_install_path}")

                assoc = data.get("associated_client", {})
                user_profile = os.environ.get("USERPROFILE", "").replace("\\", "/").rstrip("/").lower()
                best_path = _select_best_league_path(assoc, user_profile)
                if best_path:
                    _league_install_path = best_path
                    Logger.debug("Detector", f"Resolved League path: {_league_install_path}")

                _paths_resolved = True
                return _league_install_path, _riot_install_path
            except Exception as e:
                Logger.error("Detector", f"Failed to parse installs JSON at {p}: {e}")

    _paths_resolved = True
    return _league_install_path, _riot_install_path

def get_riot_executable_path() -> Optional[str]:
    """Returns the resolved absolute path to RiotClientServices.exe if found."""
    standard_target = os.path.normpath("C:\\Riot Games\\Riot Client\\RiotClientServices.exe")
    if os.path.exists(standard_target):
        return standard_target

    _, riot_dir = resolve_installation_paths()
    if riot_dir:
        exe = os.path.normpath(os.path.join(riot_dir, "RiotClientServices.exe"))
        if os.path.exists(exe):
            return exe
    return None

def get_league_executable_path() -> Optional[str]:
    """Returns the resolved absolute path to LeagueClient.exe if found."""
    league_dir, _ = resolve_installation_paths()
    if league_dir:
        exe = os.path.normpath(os.path.join(league_dir, "LeagueClient.exe"))
        if os.path.exists(exe):
            return exe
    # Fallback standard path
    fallback = os.path.normpath("C:\\Riot Games\\League of Legends\\LeagueClient.exe")
    return fallback if os.path.exists(fallback) else None

def get_league_lockfile() -> Tuple[Optional[str], Optional[str]]:
    """Reads League Client lockfile from resolved installation path."""
    league_path, _ = resolve_installation_paths()
    if not league_path:
        # Fallback to scanning common directories
        fallback_dirs = [
            "C:\\Riot Games\\League of Legends",
            "C:\\Users\\Public\\Riot Games\\League of Legends",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Riot Games", "League of Legends"),
        ]
        for d in fallback_dirs:
            if os.path.isdir(d):
                league_path = d
                break

    if league_path:
        lockfile_path = os.path.join(league_path, "lockfile")
        if os.path.exists(lockfile_path):
            try:
                with open(lockfile_path, "r", encoding="utf-8") as f:
                    data = f.read().strip().split(":")
                if len(data) >= 4:
                    return data[2], data[3]  # port, token
            except Exception as e:
                Logger.debug("Detector", f"Failed to read League lockfile: {e}")
    return None, None

def get_riot_lockfile() -> Tuple[Optional[str], Optional[str]]:
    """Reads Riot Client lockfile from LocalAppData or resolved installation path."""
    # Standard Riot Client lockfile path
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    standard_lockfile = os.path.join(local_appdata, "Riot Games", "Riot Client", "Config", "lockfile")
    
    if os.path.exists(standard_lockfile):
        try:
            with open(standard_lockfile, "r", encoding="utf-8") as f:
                data = f.read().strip().split(":")
            if len(data) >= 4:
                return data[2], data[3]
        except Exception as e:
            Logger.debug("Detector", f"Failed to read Riot standard lockfile: {e}")

    # Fallback using resolved Riot Client install path relative configuration
    _, riot_path = resolve_installation_paths()
    if riot_path:
        # Configuration directory is usually relative to the Riot Client location
        # e.g., C:/Users/Administrator/Riot Games/Riot Client/Config/lockfile
        alt_lockfile = os.path.normpath(os.path.join(riot_path, "Config", "lockfile"))
        if os.path.exists(alt_lockfile):
            try:
                with open(alt_lockfile, "r", encoding="utf-8") as f:
                    data = f.read().strip().split(":")
                if len(data) >= 4:
                    return data[2], data[3]
            except Exception as e:
                Logger.debug("Detector", f"Failed to read Riot alt lockfile: {e}")

    return None, None

def _extract_credentials_from_proc(proc: psutil.Process) -> Tuple[Optional[str], Optional[str]]:
    """Extracts port and token from a client process command line."""
    try:
        cmdline = " ".join(proc.cmdline())
        port_match = _PORT_REGEX.search(cmdline)
        token_match = _TOKEN_REGEX.search(cmdline)
        if port_match and token_match:
            return port_match.group(1), token_match.group(1)
    except psutil.AccessDenied:
        pass
    return None, None


def _apply_lockfile_fallbacks(
    league_seen: bool,
    riot_seen: bool,
    league_data: Dict[str, Any],
    riot_data: Dict[str, Any],
) -> None:
    """Fallback to lockfiles if command line parsing did not extract credentials."""
    if league_seen and (not league_data["port"] or not league_data["token"]):
        port, token = get_league_lockfile()
        if port and token:
            league_data["port"] = port
            league_data["token"] = token

    if riot_seen and (not riot_data["port"] or not riot_data["token"]):
        port, token = get_riot_lockfile()
        if port and token:
            riot_data["port"] = port
            riot_data["token"] = token


def _inspect_process_credentials(
    proc: psutil.Process,
    name: str,
    pid: Optional[int],
    target_procs: Tuple[str, ...],
    ux_name: str,
    target_data: Dict[str, Any],
) -> bool:
    """Checks a process against target process names and extracts credentials if matched."""
    if not (target_data["port"] and target_data["token"]) and name in target_procs:
        if target_data["pid"] is None or name == ux_name:
            target_data["pid"] = pid
        port, token = _extract_credentials_from_proc(proc)
        if port and token:
            target_data["port"] = port
            target_data["token"] = token
            target_data["pid"] = pid
        return True
    return False


def scan_clients(force: bool = False) -> Dict[str, Dict]:
    """
    Scans the running processes once per tick to extract ports and tokens.
    Uses cached values if called within _CACHE_TTL seconds.
    """
    global _last_scan_time, _cached_results
    now = time.time()
    if not force and (now - _last_scan_time < _CACHE_TTL):
        return _cached_results

    _last_scan_time = now

    league_seen = False
    riot_seen = False
    league_data = {"port": None, "token": None, "connected": False, "pid": None}
    riot_data = {"port": None, "token": None, "connected": False, "pid": None}

    league_procs = ("LeagueClientUx.exe", "LeagueClient.exe")
    riot_procs = ("RiotClientUx.exe", "RiotClientServices.exe")

    try:
        for proc in psutil.process_iter(attrs=["pid", "name"]):
            try:
                name = proc.info.get("name", "")
                pid = proc.info.get("pid")

                if _inspect_process_credentials(proc, name, pid, league_procs, "LeagueClientUx.exe", league_data):
                    league_seen = True
                if _inspect_process_credentials(proc, name, pid, riot_procs, "RiotClientUx.exe", riot_data):
                    riot_seen = True

                if (league_data["port"] and league_data["token"]) and (riot_data["port"] and riot_data["token"]):
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        Logger.error("Detector", f"Process scanning failed: {e}")

    _apply_lockfile_fallbacks(league_seen, riot_seen, league_data, riot_data)

    # Verify connection status
    if league_data["port"] and league_data["token"]:
        league_data["connected"] = True
    if riot_data["port"] and riot_data["token"]:
        riot_data["connected"] = True

    _cached_results = {
        "league": league_data,
        "riot": riot_data
    }
    return _cached_results


ALL_CLIENT_PROCESS_NAMES = {
    "leagueclient.exe",
    "leagueclientux.exe",
    "leagueclientuxrender.exe",
    "leaguecrashhandler.exe",
    "league of legends.exe",
    "riotclientservices.exe",
    "riotclientux.exe",
    "riotclientuxrender.exe",
    "riotclientcrashhandler.exe",
    "riot client.exe",
}


def _collect_running_client_processes() -> List[psutil.Process]:
    """Finds all active League of Legends and Riot Client processes."""
    procs = []
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name in ALL_CLIENT_PROCESS_NAMES:
                procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return procs


def terminate_all_client_instances(timeout: float = 3.0) -> int:
    """
    Terminates all running League of Legends and Riot Client processes
    to prevent stale sessions, lockfile collisions, and login errors.
    Returns the number of terminated processes.
    """
    global _last_scan_time, _cached_results
    matched_procs = _collect_running_client_processes()
    if not matched_procs:
        return 0

    killed_count = len(matched_procs)
    try:
        # Pass 1: Graceful termination
        for proc in matched_procs:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        # Wait for processes to exit
        _, alive = psutil.wait_procs(matched_procs, timeout=timeout)

        # Pass 2: Forceful kill for any remaining processes
        for proc in alive:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        # Reset detector cache
        _last_scan_time = 0.0
        _cached_results = {
            "league": {"port": None, "token": None, "connected": False, "pid": None},
            "riot": {"port": None, "token": None, "connected": False, "pid": None}
        }

        # Brief settle delay for Windows file handles & sockets to release
        time.sleep(0.3)

        Logger.action(
            "Detector",
            f"Terminated {killed_count} running client process(es) before launch.",
            count=killed_count
        )
    except Exception as e:
        Logger.error("Detector", f"Failed to terminate client processes: {e}")

    return killed_count
