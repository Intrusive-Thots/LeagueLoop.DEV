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
            import re
            if re.search(r"\b(ERROR|CRITICAL)\b", sline):
                result["recent_errors"].append(sline)
            elif re.search(r"\bWARNING\b", sline) and "[LCU_WS_ANOMALY]" not in sline and "[LCU_NETWORK_THROTTLE]" not in sline:
                result["recent_warnings"].append(sline)
    except Exception as e:
        result["error_reading"] = str(e)

    return result


def inspect_crash_log(path: Path, max_sessions: int = 5) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "exists": path.exists(),
        "recent_crashes": [],
        "total_sessions_tracked": 0,
        "total_actual_crashes": 0,
        "total_crash_sessions": 0,
    }
    if not path.exists():
        return result

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        import re
        parts = re.split(r"(--- session [^\n]+ ---)", content)
        sessions: List[str] = []
        crashes: List[Dict[str, Any]] = []

        current_header = ""
        for part in parts:
            part_stripped = part.strip()
            if not part_stripped:
                continue
            if part_stripped.startswith("--- session "):
                current_header = part_stripped
                sessions.append(current_header)
            elif current_header:
                lower_body = part_stripped.lower()
                if any(k in lower_body for k in ("fatal exception", "traceback", "thread 0x", "access violation", "segmentation fault")):
                    lines = [l.strip() for l in part_stripped.splitlines() if l.strip()]
                    summary = lines[0] if lines else "Fatal exception detected"
                    crashes.append({
                        "session": current_header,
                        "summary": summary,
                        "details": lines[:5],
                    })

        result["total_sessions_tracked"] = len(sessions)
        result["total_actual_crashes"] = len(crashes)
        recent_headers = set(sessions[-max_sessions:]) if sessions else set()
        recent_crashes = [c for c in crashes if c["session"] in recent_headers]
        result["recent_crashes"] = recent_crashes
        result["total_crash_sessions"] = len(recent_crashes)
        if crashes:
            result["latest_historical_crash"] = crashes[-1]
    except Exception as e:
        result["error_reading"] = str(e)

    return result


def inspect_session_log(path: Path, max_entries: int = 20) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "exists": path.exists(),
        "total_entries": 0,
        "recent_entries": [],
        "level_counts": {},
        "active_sessions": [],
        "recent_anomalies_or_throttles": [],
    }
    if not path.exists():
        return result

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = [l.strip() for l in f if l.strip()]
        result["total_entries"] = len(lines)
        tail = lines[-max_entries:] if len(lines) > max_entries else lines

        parsed_entries = []
        sessions_seen = set()
        level_counts: Dict[str, int] = {}
        anomalies = []

        for line in tail:
            try:
                entry = json.loads(line)
                parsed_entries.append(entry)
                lvl = entry.get("level", "UNKNOWN")
                level_counts[lvl] = level_counts.get(lvl, 0) + 1
                if "session" in entry:
                    sessions_seen.add(entry["session"])
                tag = entry.get("tag", "")
                if "THROTTLE" in tag or "ANOMALY" in tag or lvl in ("WARNING", "ERROR", "CRITICAL"):
                    anomalies.append({
                        "ts": entry.get("ts"),
                        "level": lvl,
                        "tag": tag,
                        "msg": entry.get("msg", ""),
                    })
            except Exception:
                continue

        result["recent_entries"] = parsed_entries
        result["level_counts"] = level_counts
        result["active_sessions"] = sorted(list(sessions_seen))
        result["recent_anomalies_or_throttles"] = anomalies
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


def run_diagnostics(
    paths: Optional[Dict[str, Path]] = None,
    max_lines: int = 30,
    max_sessions: int = 5,
    max_screenshots: int = 5,
) -> Dict[str, Any]:
    p = paths or get_leagueloop_paths()
    errors_info = inspect_error_log(p["error_log"], max_lines=max_lines)
    crashes_info = inspect_crash_log(p["crash_log"], max_sessions=max_sessions)
    session_info = inspect_session_log(p["session_log"], max_entries=max_lines)
    screenshots_info = inspect_screenshots(p["screenshots"], max_count=max_screenshots)

    healthy = (
        len(errors_info.get("recent_errors", [])) == 0
        and errors_info.get("network_throttles_count", 0) == 0
        and not any(e.get("level") in ("ERROR", "CRITICAL") for e in session_info.get("recent_anomalies_or_throttles", []))
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "healthy": healthy,
        "logs_path": str(p["logs"]),
        "screenshots_path": str(p["screenshots"]),
        "error_analysis": errors_info,
        "crash_analysis": crashes_info,
        "session_analysis": session_info,
        "recent_screenshots": screenshots_info,
    }


def main():
    parser = argparse.ArgumentParser(description="LeagueLoop Automated Diagnostics")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--summary", action="store_true", default=True, help="Print human-readable summary")
    parser.add_argument("--max-lines", "--lines", "-n", type=int, default=30, help="Number of error.log lines to inspect (default: 30)")
    parser.add_argument("--max-sessions", type=int, default=5, help="Number of crash sessions to inspect (default: 5)")
    parser.add_argument("--max-screenshots", type=int, default=5, help="Number of screenshots to inspect (default: 5)")
    args = parser.parse_args()

    diag = run_diagnostics(
        max_lines=args.max_lines,
        max_sessions=args.max_sessions,
        max_screenshots=args.max_screenshots,
    )

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

    sa = diag.get("session_analysis", {})
    if sa.get("exists"):
        print(f"\n[Session Log Inspection]")
        print(f"  Total Session Entries: {sa.get('total_entries', 0)}")
        print(f"  Levels (tail): {sa.get('level_counts', {})}")
        print(f"  Active Sessions: {sa.get('active_sessions', [])}")
        if sa.get("recent_anomalies_or_throttles"):
            print(f"  Recent Anomalies/Throttles: {len(sa['recent_anomalies_or_throttles'])}")
            for a in sa["recent_anomalies_or_throttles"][:3]:
                print(f"    - [{a.get('level')}] {a.get('tag')}: {a.get('msg')}")

    ca = diag["crash_analysis"]
    print(f"\n[Crash Inspection]")
    print(f"  Sessions Tracked (faulthandler): {ca.get('total_sessions_tracked', 0)}")
    print(f"  Historical Crashes: {ca.get('total_actual_crashes', 0)}")
    print(f"  Recent Crashes (last 5 sessions): {len(ca.get('recent_crashes', []))}")
    for c in ca.get("recent_crashes", []):
        print(f"    - {c.get('session')}: {c.get('summary')}")
    if ca.get("latest_historical_crash") and not ca.get("recent_crashes"):
        lhc = ca["latest_historical_crash"]
        print(f"  Last Historical Crash: {lhc.get('session')} ({lhc.get('summary')})")

    print(f"\n[Screenshots Inspection]")
    print(f"  Recent Captures: {len(diag['recent_screenshots'])}")
    for s in diag["recent_screenshots"]:
        print(f"    - {s.get('filename')} ({s.get('modified', '')})")

    sys.exit(0 if diag["healthy"] else 1)


if __name__ == "__main__":
    main()
