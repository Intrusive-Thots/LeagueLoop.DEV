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
    Resolves official installation directories and executable locations for
    both the League of Legends Client and the Riot Client.
    Returns: (league_install_path, riot_install_path)
    """
    global _league_install_path, _riot_install_path, _paths_resolved
    if _paths_resolved and _league_install_path and _riot_install_path:
        return _league_install_path, _riot_install_path

    # 1. Parse RiotClientInstalls.json
    paths_to_try = [
        os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "Riot Games", "RiotClientInstalls.json"),
        os.path.join(os.environ.get("ALLUSERSPROFILE", "C:\\ProgramData"), "Riot Games", "RiotClientInstalls.json"),
    ]

    for p in paths_to_try:
        if os.path.exists(p) and os.path.getsize(p) > 2:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)

                rc_path = data.get("rc_default") or data.get("rc_live")
                if rc_path:
                    rc_path = os.path.normpath(rc_path)
                    _riot_install_path = os.path.dirname(rc_path)

                assoc = data.get("associated_client", {})
                for game_path in assoc.keys():
                    if "league of legends" in game_path.lower():
                        _league_install_path = os.path.normpath(game_path)
                        break
            except Exception as e:
                Logger.debug("Detector", f"Failed parsing RiotClientInstalls.json: {e}")

    # 2. Registry Lookup Fallback
    try:
        import winreg
        for hkey in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            if not _league_install_path:
                try:
                    key = winreg.OpenKey(hkey, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game league_of_legends.live")
                    val, _ = winreg.QueryValueEx(key, "InstallLocation")
                    if val and os.path.exists(val):
                        _league_install_path = os.path.normpath(val)
                except Exception:
                    pass

            if not _riot_install_path:
                try:
                    key = winreg.OpenKey(hkey, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game riot_client.live")
                    val, _ = winreg.QueryValueEx(key, "UninstallString")
                    if val:
                        clean_p = val.split('"')[1] if '"' in val else val.split(' ')[0]
                        if os.path.exists(clean_p):
                            _riot_install_path = os.path.dirname(os.path.normpath(clean_p))
                except Exception:
                    pass
    except Exception:
        pass

    # 3. Common Drive Root Scanning Fallback
    drives = ["C:", "D:", "E:", "F:", "G:"]
    if not _league_install_path:
        for d in drives:
            candidate = os.path.join(d + "\\", "Riot Games", "League of Legends")
            if os.path.exists(os.path.join(candidate, "LeagueClient.exe")):
                _league_install_path = candidate
                break

    if not _riot_install_path:
        for d in drives:
            candidate = os.path.join(d + "\\", "Riot Games", "Riot Client")
            if os.path.exists(os.path.join(candidate, "RiotClientServices.exe")):
                _riot_install_path = candidate
                break

    _paths_resolved = True
    Logger.debug("Detector", f"Resolved paths - League: {_league_install_path}, Riot: {_riot_install_path}")
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

_game_running_cache: Optional[bool] = None
_last_game_check = 0.0
_cached_game_pid: Optional[int] = None

def is_game_running() -> bool:
    """Unified check if League of Legends.exe (the game) is running with caching."""
    global _game_running_cache, _last_game_check, _cached_game_pid
    now = time.time()

    # 1. Fast-path: check cached PID
    if _cached_game_pid is not None:
        try:
            p = psutil.Process(_cached_game_pid)
            if p.is_running() and p.name().lower() == "league of legends.exe":
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        _cached_game_pid = None

    # 2. Throttle scan to once per 2 seconds
    if _last_game_check > 0 and (now - _last_game_check < 2.0):
        return bool(_game_running_cache)

    _last_game_check = now
    _game_running_cache = False

    try:
        for p in psutil.process_iter(attrs=["pid", "name"]):
            try:
                pname = p.info.get("name")
                if pname and pname.lower() == "league of legends.exe":
                    _cached_game_pid = p.info.get("pid")
                    _game_running_cache = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, KeyError):
                continue
    except Exception as e:
        Logger.debug("Detector", f"Process scan for game failed: {e}")

    return _game_running_cache


def safe_launch_exe(exe_path: str, args_str: str = "") -> bool:
    """Helper to safely launch an executable on Windows with UAC elevation fallback."""
    if not os.path.exists(exe_path):
        return False

    import subprocess
    try:
        cmd = [exe_path]
        if args_str:
            cmd.extend(args_str.split())
        subprocess.Popen(cmd)
        return True
    except (OSError, PermissionError) as e:
        Logger.debug("Detector", f"Popen failed ({e}), trying ShellExecuteW...")
    except Exception as e:
        Logger.debug("Detector", f"Popen error: {e}")

    try:
        import ctypes
        res = ctypes.windll.shell32.ShellExecuteW(None, "open", exe_path, args_str or None, None, 1)
        if res > 32:
            return True
    except Exception as e:
        Logger.debug("Detector", f"ShellExecuteW 'open' failed: {e}")

    try:
        import ctypes
        res = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, args_str or None, None, 1)
        if res > 32:
            return True
    except Exception as e:
        Logger.error("Detector", f"ShellExecuteW 'runas' failed for {exe_path}: {e}")

    return False


def launch_league_client() -> Tuple[bool, str]:
    """
    Launches the League of Legends Client / Riot Client if not already running.
    Returns: (success: bool, message: str)
    """
    scan = scan_clients(force=True)
    if scan.get("league", {}).get("connected"):
        return True, "League Client is already running!"

    league_path, riot_path = resolve_installation_paths()

    # 1. Try launching Riot Client with League launch command
    if riot_path:
        rc_exe = os.path.join(riot_path, "RiotClientServices.exe")
        if os.path.exists(rc_exe):
            if safe_launch_exe(rc_exe, "--launch-product=league_of_legends --launch-patchline=live"):
                Logger.info("Detector", f"Launched League via RiotClientServices.exe at {rc_exe}")
                return True, "Launching League of Legends via Riot Client..."

    # 2. Try launching LeagueClient.exe directly
    if league_path:
        league_exe = os.path.join(league_path, "LeagueClient.exe")
        if os.path.exists(league_exe):
            if safe_launch_exe(league_exe):
                Logger.info("Detector", f"Launched LeagueClient.exe directly at {league_exe}")
                return True, "Launching LeagueClient.exe..."

    # 3. Fallback standard default paths
    fallback_paths = [
        "C:\\Riot Games\\Riot Client\\RiotClientServices.exe",
        "C:\\Riot Games\\League of Legends\\LeagueClient.exe",
    ]
    for p in fallback_paths:
        if os.path.exists(p):
            args_str = "--launch-product=league_of_legends --launch-patchline=live" if "RiotClientServices" in p else ""
            if safe_launch_exe(p, args_str):
                return True, f"Launched client from fallback path: {p}"

    return False, "Could not find Riot Client or League of Legends installation path."
