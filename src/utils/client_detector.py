"""
Client Detector Utility
───────────────────────
Provides unified, cached process detection and installation path resolution
for both the Riot Client and the League of Legends Client.
"""
import json
import os
import time
import psutil
from typing import Dict, Optional, Tuple
from utils.logger import Logger

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

def resolve_installation_paths() -> Tuple[Optional[str], Optional[str]]:
    """
    Parses RiotClientInstalls.json to resolve installation directories.
    Returns: (league_install_path, riot_install_path)
    """
    global _league_install_path, _riot_install_path, _paths_resolved
    if _paths_resolved:
        return _league_install_path, _riot_install_path

    # Try standard paths for RiotClientInstalls.json
    paths_to_try = [
        os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "Riot Games", "RiotClientInstalls.json"),
        os.path.join(os.environ.get("ALLUSERSPROFILE", "C:\\ProgramData"), "Riot Games", "RiotClientInstalls.json"),
    ]

    for p in paths_to_try:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Resolve Riot Client executable and its directory
                rc_path = data.get("rc_default") or data.get("rc_live")
                if rc_path:
                    # Convert to standard Windows backslashes
                    rc_path = os.path.normpath(rc_path)
                    _riot_install_path = os.path.dirname(rc_path)
                    Logger.debug("Detector", f"Resolved Riot Client path: {_riot_install_path}")

                # Resolve League of Legends install path
                assoc = data.get("associated_client", {})
                for game_path in assoc.keys():
                    if "league of legends" in game_path.lower():
                        _league_install_path = os.path.normpath(game_path)
                        Logger.debug("Detector", f"Resolved League path: {_league_install_path}")
                        break

                _paths_resolved = True
                return _league_install_path, _riot_install_path
            except Exception as e:
                Logger.error("Detector", f"Failed to parse installs JSON at {p}: {e}")

    # Fallback to defaults if parsing fails
    _paths_resolved = True
    return _league_install_path, _riot_install_path

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

    # Reset temp states
    league_found = False
    riot_found = False
    league_data = {"port": None, "token": None, "connected": False, "pid": None}
    riot_data = {"port": None, "token": None, "connected": False, "pid": None}

    # Process lists we care about
    league_procs = ["LeagueClientUx.exe", "LeagueClient.exe"]
    riot_procs = ["RiotClientServices.exe", "RiotClientUx.exe"]

    try:
        # Perform single process iteration pass
        for proc in psutil.process_iter(attrs=["pid", "name"]):
            try:
                name = proc.info.get("name", "")
                pid = proc.info.get("pid")
                
                # Check for League of Legends client
                if not league_found and name in league_procs:
                    league_data["pid"] = pid
                    # Try to extract credentials from command line
                    try:
                        cmdline = proc.cmdline()
                        for arg in cmdline:
                            if arg.startswith("--app-port="):
                                league_data["port"] = arg.split("=", 1)[1]
                            elif arg.startswith("--remoting-auth-token="):
                                league_data["token"] = arg.split("=", 1)[1]
                            if league_data["port"] and league_data["token"]:
                                break
                    except psutil.AccessDenied:
                        pass  # Handled below by lockfile fallback
                    
                    league_found = True

                # Check for Riot Client
                if not riot_found and name in riot_procs:
                    riot_data["pid"] = pid
                    # Try to extract credentials from command line
                    try:
                        cmdline = proc.cmdline()
                        for arg in cmdline:
                            if arg.startswith("--app-port="):
                                riot_data["port"] = arg.split("=", 1)[1]
                            elif arg.startswith("--remoting-auth-token="):
                                riot_data["token"] = arg.split("=", 1)[1]
                            if riot_data["port"] and riot_data["token"]:
                                break
                    except psutil.AccessDenied:
                        pass
                    
                    riot_found = True

                # Stop iteration early if both are fully resolved
                if league_found and riot_found:
                    break

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        Logger.error("Detector", f"Process scanning failed: {e}")

    # Fallback 1: League Client credentials from lockfile
    if league_found and (not league_data["port"] or not league_data["token"]):
        port, token = get_league_lockfile()
        if port and token:
            league_data["port"] = port
            league_data["token"] = token

    # Fallback 2: Riot Client credentials from lockfile
    if riot_found and (not riot_data["port"] or not riot_data["token"]):
        port, token = get_riot_lockfile()
        if port and token:
            riot_data["port"] = port
            riot_data["token"] = token

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
