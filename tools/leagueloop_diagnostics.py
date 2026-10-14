#!/usr/bin/env python3
"""
leagueloop_diagnostics.py — Autonomous Diagnostic Suite for LeagueLoop.DEV

Performs automated log and screenshot inspection compliant with the LeagueLoop.DEV
protocol:
  - %LOCALAPPDATA%\\LeagueLoop\\logs\\error.log (Tracebacks, Errors, Warnings)
  - %LOCALAPPDATA%\\LeagueLoop\\logs\\crash.log (Fatal exits)
  - %LOCALAPPDATA%\\LeagueLoop\\logs\\debug.log (Execution context)
  - %LOCALAPPDATA%\\LeagueLoop\\debug_screenshots\\ (Recent UI action captures)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def get_leagueloop_paths() -> Dict[str, Path]:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    base = Path(local_app_data) / "LeagueLoop" if local_app_data else Path.home() / "AppData" / "Local" / "LeagueLoop"
    return {
        "base": base,
        "logs": base / "logs",
        "screenshots": base / "debug_screenshots",
        "error_log": base / "logs" / "error.log",
        "crash_log": base / "logs" / "crash.log",
        "debug_log": base / "logs" / "debug.log",
        "session_log": base / "logs" / "session.jsonl",
    }


def inspect_error_log(path: Path, max_lines: int = 30) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "exists": path.exists(),
        "recent_errors": [],
        "recent_warnings": [],
        "ws_anomalies_count": 0,
        "network_throttles_count": 0,
        "total_lines_inspected": 0,
    }
    if not path.exists():
        return result

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        result["total_lines_inspected"] = len(lines)
        tail = lines[-max_lines:] if len(lines) > max_lines else lines

        for line in tail:
            sline = line.strip()
            if not sline:
                continue
            if "[LCU_WS_ANOMALY]" in sline:
                result["ws_anomalies_count"] += 1
            if "[LCU_NETWORK_THROTTLE]" in sline:
                result["network_throttles_count"] += 1
            if " ERROR " in sline or " CRITICAL " in sline:
                result["recent_errors"].append(sline)
            elif " WARNING " in sline and "[LCU_WS_ANOMALY]" not in sline and "[LCU_NETWORK_THROTTLE]" not in sline:
                result["recent_warnings"].append(sline)
    except Exception as e:
        result["error_reading"] = str(e)

    return result


def inspect_crash_log(path: Path, max_sessions: int = 5) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "exists": path.exists(),
        "recent_crashes": [],
        "total_crash_sessions": 0,
    }
    if not path.exists():
        return result

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        session_lines = [l.strip() for l in lines if l.strip().startswith("--- session ")]
        result["total_crash_sessions"] = len(session_lines)
        result["recent_crashes"] = session_lines[-max_sessions:]
    except Exception as e:
        result["error_reading"] = str(e)

    return result


def inspect_screenshots(path: Path, max_count: int = 5) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    captures = []
    try:
        files = sorted(path.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files[:max_count]:
            stat = f.stat()
            captures.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    except Exception as e:
        captures.append({"error_reading": str(e)})

    return captures


def run_diagnostics(paths: Optional[Dict[str, Path]] = None) -> Dict[str, Any]:
    p = paths or get_leagueloop_paths()
    errors_info = inspect_error_log(p["error_log"])
    crashes_info = inspect_crash_log(p["crash_log"])
    screenshots_info = inspect_screenshots(p["screenshots"])

    healthy = (
        len(errors_info.get("recent_errors", [])) == 0
        and errors_info.get("network_throttles_count", 0) == 0
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "healthy": healthy,
        "logs_path": str(p["logs"]),
        "screenshots_path": str(p["screenshots"]),
        "error_analysis": errors_info,
        "crash_analysis": crashes_info,
        "recent_screenshots": screenshots_info,
    }


def main():
    parser = argparse.ArgumentParser(description="LeagueLoop Automated Diagnostics")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--summary", action="store_true", default=True, help="Print human-readable summary")
    args = parser.parse_args()

    diag = run_diagnostics()

    if args.json:
        print(json.dumps(diag, indent=2))
        sys.exit(0 if diag["healthy"] else 1)

    print("=== LeagueLoop Diagnostics ===")
    print(f"Status: {'[HEALTHY]' if diag['healthy'] else '[NEEDS ATTENTION]'}")
    print(f"Logs Path: {diag['logs_path']}")
    print(f"Screenshots Path: {diag['screenshots_path']}")

    ea = diag["error_analysis"]
    print(f"\n[Logs Inspection]")
    print(f"  Recent Errors: {len(ea.get('recent_errors', []))}")
    for err in ea.get("recent_errors", []):
        print(f"    - {err}")
    print(f"  Recent Warnings: {len(ea.get('recent_warnings', []))}")
    for warn in ea.get("recent_warnings", []):
        print(f"    - {warn}")
    print(f"  WS Anomalies (tail): {ea.get('ws_anomalies_count', 0)}")
    print(f"  Network Throttles (tail): {ea.get('network_throttles_count', 0)}")

    ca = diag["crash_analysis"]
    print(f"\n[Crash Inspection]")
    print(f"  Total Crash Sessions Logged: {ca.get('total_crash_sessions', 0)}")
    if ca.get("recent_crashes"):
        print(f"  Latest: {ca['recent_crashes'][-1]}")

    print(f"\n[Screenshots Inspection]")
    print(f"  Recent Captures: {len(diag['recent_screenshots'])}")
    for s in diag["recent_screenshots"]:
        print(f"    - {s.get('filename')} ({s.get('modified', '')})")

    sys.exit(0 if diag["healthy"] else 1)


if __name__ == "__main__":
    main()
