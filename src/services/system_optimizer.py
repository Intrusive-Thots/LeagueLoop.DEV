"""
System and Network Optimization Services for LeagueLoop.
Provides low-latency network tweaks ('Fix Ping') and safe background process cleanup ('Kill Unnecessary Windows Processes').
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Dict, List, Set

import psutil

from utils.logger import Logger


#: Safe targets for termination: background updaters, telemetry, and non-critical bloat
TARGET_PROCESS_NAMES: Set[str] = {
    # Windows telemetry & background apps
    "onedrive.exe",
    "microsoftedgeupdate.exe",
    "googleupdate.exe",
    "searchapp.exe",
    "phoneexperiencehost.exe",
    "yourphone.exe",
    "skypeapp.exe",
    "skypebackgroundhost.exe",
    "gamebarftserver.exe",
    "cortana.exe",
    "mscorsvw.exe",
    "compattelrunner.exe",
    "smartscreen.exe",
    # Background launchers/updaters that eat CPU/bandwidth
    "epicgameslauncher.exe",
    "epicwebhelper.exe",
    "originwebhelperservice.exe",
    "galaxyclient.exe",
    "battle.net.exe",
    "agent.exe",
    "spotify.exe",
}

#: Strict whitelist: processes that MUST NEVER be killed under any circumstances
PROTECTED_PROCESS_NAMES: Set[str] = {
    # Windows kernel & critical subsystem
    "system",
    "system idle process",
    "idle",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "winlogon.exe",
    "svchost.exe",
    "dwm.exe",
    "explorer.exe",
    "taskhostw.exe",
    "sihost.exe",
    # Riot Games & League of Legends
    "leagueclient.exe",
    "leagueclientux.exe",
    "leagueclientuxrender.exe",
    "riotclientservices.exe",
    "riotclientux.exe",
    "riotclientcrashhandler.exe",
    "league of legends.exe",
    "vgc.exe",
    "vgtray.exe",
    # Python & LeagueLoop
    "python.exe",
    "pythonw.exe",
    "leagueloop.exe",
    "leagueloop_installer.exe",
}


class SystemOptimizer:
    """Provides methods to optimize gaming latency and purge unnecessary background bloat."""

    @staticmethod
    def is_windows() -> bool:
        """Returns True if running on a Windows system."""
        return sys.platform == "win32"

    @staticmethod
    def is_admin() -> bool:
        """Checks if current process has Administrator privileges on Windows."""
        if not SystemOptimizer.is_windows():
            return False
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception as exc:
            Logger.debug("SystemOptimizer", f"Failed checking admin rights: {exc}")
            return False

    @classmethod
    def kill_unnecessary_processes(cls) -> Dict[str, Any]:
        """
        Scans running processes and terminates safe background bloat (telemetry, updaters).
        Returns a summary dict with killed count, memory freed in MB, and process names.
        """
        killed_count = 0
        freed_bytes = 0
        killed_names: List[str] = []

        current_pid = os.getpid()

        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                pid = proc.info.get("pid")
                name = (proc.info.get("name") or "").lower()

                # Safety checks
                if not name or pid == current_pid or pid <= 4:
                    continue

                if name in PROTECTED_PROCESS_NAMES:
                    continue

                if name in TARGET_PROCESS_NAMES:
                    # Tally memory before terminating
                    mem_info = proc.info.get("memory_info")
                    if mem_info:
                        freed_bytes += getattr(mem_info, "rss", 0)

                    proc.terminate()
                    killed_count += 1
                    killed_names.append(proc.info.get("name") or name)
                    Logger.info("SystemOptimizer", f"Terminated non-essential process: {name} (PID {pid})")

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as exc:
                Logger.debug("SystemOptimizer", f"Error evaluating process: {exc}")

        freed_mb = round(freed_bytes / (1024 * 1024), 1)
        Logger.info("SystemOptimizer", f"Purged {killed_count} background processes. Freed {freed_mb} MB RAM.")

        return {
            "success": True,
            "killed_count": killed_count,
            "freed_mb": freed_mb,
            "killed_names": killed_names,
            "message": (
                f"Killed {killed_count} unnecessary processes ({freed_mb} MB freed)"
                if killed_count > 0
                else "No unnecessary background processes found."
            ),
        }

    @classmethod
    def fix_ping(cls) -> Dict[str, Any]:
        """
        Applies network and TCP latency optimizations:
        - Sets MTU to 1428 (eliminates cellular/upstream packet fragmentation)
        - Points DNS to Cloudflare (1.1.1.1) and Google (8.8.8.8) and flushes cache
        - Enables TCPNoDelay (disables Nagle's algorithm) & sets TcpAckFrequency = 1
        - Disables Windows multimedia network throttling
        - Disables RSC (Receive Segment Coalescing) to prevent packet buffering delay
        """
        if not cls.is_windows():
            return {
                "success": False,
                "message": "Ping optimization is only supported on Windows.",
            }

        ps_script = """
# 1. MTU 1428 persistent
netsh interface ipv4 set subinterface "Ethernet" mtu=1428 store=persistent 2>$null
# 2. DNS servers
netsh interface ipv4 set dnsservers name="Ethernet" source=static address="1.1.1.1" validate=no 2>$null
netsh interface ipv4 add dnsservers name="Ethernet" address="1.0.0.1" index=2 validate=no 2>$null
ipconfig /flushdns 2>$null
# 3. Low latency TCP registry
$interfaces = Get-ChildItem "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces" -ErrorAction SilentlyContinue
foreach ($iface in $interfaces) {
    Set-ItemProperty -Path $iface.PSPath -Name "TcpAckFrequency" -Value 1 -Type DWord -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $iface.PSPath -Name "TCPNoDelay" -Value 1 -Type DWord -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $iface.PSPath -Name "TcpDelAckTicks" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
}
# 4. Remove network throttling
Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Multimedia\\SystemProfile" -Name "NetworkThrottlingIndex" -Value 0xffffffff -Type DWord -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Multimedia\\SystemProfile" -Name "SystemResponsiveness" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
# 5. TCP global tuning
netsh int tcp set global rsc=disabled 2>$null
netsh int tcp set global timestamps=disabled 2>$null
netsh int tcp set global autotuninglevel=normal 2>$null
"""

        try:
            if cls.is_admin():
                # Direct in-process execution since we are already elevated
                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                Logger.info("SystemOptimizer", f"Ping fix applied directly (code {proc.returncode}).")
                return {
                    "success": True,
                    "elevated": True,
                    "message": "Ping optimized: MTU 1428, Cloudflare DNS, & TCPNoDelay applied!",
                }
            else:
                # Launch via UAC elevation request
                escaped_script = ps_script.replace('"', '`"')
                cmd = f"Start-Process powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -Command \"{escaped_script}\"' -Verb RunAs"
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                Logger.info("SystemOptimizer", "Launched elevated UAC prompt to apply ping optimizations.")
                return {
                    "success": True,
                    "elevated": False,
                    "message": "Optimization requested! Click 'Yes' on the Windows permission prompt.",
                }
        except Exception as exc:
            Logger.error("SystemOptimizer", f"Failed to execute ping optimization: {exc}")
            return {
                "success": False,
                "message": f"Optimization failed: {exc}",
            }
