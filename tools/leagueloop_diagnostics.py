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

from collections import deque

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def read_tail_bounded(path: Path, max_lines: int = 30) -> tuple[int, List[str]]:
    """Memory-bounded line counter and tail reader using collections.deque."""
    if not path.exists():
        return 0, []
    count = 0
    q: deque = deque(maxlen=max_lines)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                count += 1
                q.append(line)
    except Exception:
        return 0, []
    return count, list(q)


def get_leagueloop_paths() -> Dict[str, Path]:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    base = Path(local_app_data) / "LeagueLoop" if local_app_data else Path.home() / "AppData" / "Local" / "LeagueLoop"
    return {
        "base": base,
        "logs": base / "logs",
        "screenshots": base / "debug_screenshots",
        "fallback_screenshots": Path.home() / "Desktop" / "Captures",
        "error_log": base / "logs" / "error.log",
        "crash_log": base / "logs" / "crash.log",
        "debug_log": base / "logs" / "debug.log",
        "session_log": base / "logs" / "session.jsonl",
    }


def inspect_error_log(path: Path, max_lines: int = 30, include_rotated: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "exists": path.exists(),
        "recent_errors": [],
        "recent_warnings": [],
        "ws_anomalies_count": 0,
        "network_throttles_count": 0,
        "total_lines_inspected": 0,
        "rotated_log_inspected": False,
    }
    if not path.exists():
        return result

    try:
        total_count, tail = read_tail_bounded(path, max_lines=max_lines)
        result["total_lines_inspected"] = total_count

        if (include_rotated or total_count < max_lines):
            rotated_path = path.parent / f"{path.name}.1"
            if rotated_path.exists():
                needed = max_lines - len(tail)
                if needed > 0:
                    _, rot_tail = read_tail_bounded(rotated_path, max_lines=needed)
                    tail = rot_tail + tail
                    result["rotated_log_inspected"] = True

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
        sessions: List[str] = []
        crashes: List[Dict[str, Any]] = []
        current_header = ""
        current_body: List[str] = []

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                sline = line.strip()
                if sline.startswith("--- session ") and sline.endswith(" ---"):
                    if current_header and current_body:
                        body_text = " ".join(current_body).lower()
                        if any(k in body_text for k in ("fatal exception", "traceback", "thread 0x", "access violation", "segmentation fault")):
                            summary = current_body[0] if current_body else "Fatal exception detected"
                            crashes.append({
                                "session": current_header,
                                "summary": summary,
                                "details": current_body[:5],
                            })
                    current_header = sline
                    sessions.append(current_header)
                    current_body = []
                elif current_header and sline:
                    current_body.append(sline)

        # Process the final session block
        if current_header and current_body:
            body_text = " ".join(current_body).lower()
            if any(k in body_text for k in ("fatal exception", "traceback", "thread 0x", "access violation", "segmentation fault")):
                summary = current_body[0] if current_body else "Fatal exception detected"
                crashes.append({
                    "session": current_header,
                    "summary": summary,
                    "details": current_body[:5],
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
        total_count, tail = read_tail_bounded(path, max_lines=max_entries)
        result["total_entries"] = total_count

        parsed_entries = []
        sessions_seen = set()
        level_counts: Dict[str, int] = {}
        anomalies = []

        for line in tail:
            sline = line.strip()
            if not sline:
                continue
            try:
                entry = json.loads(sline)
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


def inspect_debug_log(path: Path, max_lines: int = 30) -> Dict[str, Any]:
    """Inspects recent execution context from debug.log using bounded streaming."""
    result: Dict[str, Any] = {
        "exists": path.exists(),
        "total_lines_inspected": 0,
        "recent_entries": [],
        "level_counts": {},
        "diagnostic_tags_count": 0,
        "recent_diagnostics": [],
    }
    if not path.exists():
        return result

    try:
        total_count, tail = read_tail_bounded(path, max_lines=max_lines)
        result["total_lines_inspected"] = total_count

        level_counts: Dict[str, int] = {}
        recent_entries = []
        recent_diagnostics = []

        import re
        for line in tail:
            sline = line.strip()
            if not sline:
                continue
            recent_entries.append(sline)
            m_level = re.search(r"\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b", sline)
            if m_level:
                lvl = m_level.group(1)
                level_counts[lvl] = level_counts.get(lvl, 0) + 1

            if any(tag in sline for tag in ("[LCU_DIAGNOSTICS]", "[LCU_WS_ANOMALY]", "[LCU_NETWORK_THROTTLE]")):
                result["diagnostic_tags_count"] += 1
                recent_diagnostics.append(sline)

        result["level_counts"] = level_counts
        result["recent_entries"] = recent_entries
        result["recent_diagnostics"] = recent_diagnostics
    except Exception as e:
        result["error_reading"] = str(e)

    return result


def classify_screenshot_event(filename: str) -> tuple[str, str]:
    """Classifies screenshot filename according to LeagueLoop.DEV protocol.
    
    Returns (category, event_label).
    Categories:
      - 'button_click': UI button clicks (e.g. find_match_clicked)
      - 'tab_transition': Tab switching (e.g. tab_switch)
      - 'champion_action': Champion hover/lock attempts (e.g. champion_hover, champion_lock)
      - 'game_phase_change': Phase changes (e.g. game_phase_change)
      - 'queue_action': Queue search / matchmaking (e.g. queue_search_started)
      - 'hotkey_setting': Hotkey interactions (e.g. setting_hotkey_find_match)
      - 'general_ui': Other captures
    """
    stem = Path(filename).stem
    import re
    cleaned = re.sub(r"^\d{8}_\d{6}_?", "", stem)
    cleaned_lower = cleaned.lower()

    if "click" in cleaned_lower:
        return "button_click", cleaned
    elif "tab" in cleaned_lower:
        return "tab_transition", cleaned
    elif any(k in cleaned_lower for k in ("champ", "hover", "lock")):
        return "champion_action", cleaned
    elif any(k in cleaned_lower for k in ("phase", "game_phase")):
        return "game_phase_change", cleaned
    elif "queue" in cleaned_lower:
        return "queue_action", cleaned
    elif "hotkey" in cleaned_lower:
        return "hotkey_setting", cleaned
    return "general_ui", cleaned


def format_human_age(seconds: float) -> str:
    """Formats elapsed seconds into a compact human-readable duration."""
    if seconds < 0:
        return "in the future"
    if seconds < 60:
        return f"{int(seconds)}s ago"
    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)}m ago"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f}h ago"
    days = hours / 24
    return f"{days:.1f}d ago"


def inspect_screenshots(
    path: Path,
    max_count: int = 5,
    fallback_path: Optional[Path] = None,
    now: Optional[datetime] = None,
    max_age_hours: Optional[float] = None,
) -> List[Dict[str, Any]]:
    files = []
    source = "primary"
    if path.exists():
        files = sorted(path.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not files and fallback_path and fallback_path.exists():
        fallback_files = sorted(fallback_path.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        if fallback_files:
            files = fallback_files
            source = "fallback"

    ref_now = now or datetime.now()
    ref_ts = ref_now.timestamp()

    captures = []
    try:
        for f in files[:max_count]:
            stat = f.stat()
            cat, event_label = classify_screenshot_event(f.name)
            is_corrupted = (stat.st_size == 0)
            age_secs = max(0.0, round(ref_ts - stat.st_mtime, 1))
            age_human = format_human_age(age_secs)
            is_stale = (max_age_hours is not None and age_secs > (max_age_hours * 3600))
            captures.append({
                "filename": f.name,
                "category": cat,
                "event_label": event_label,
                "source": source,
                "size_bytes": stat.st_size,
                "is_corrupted": is_corrupted,
                "age_seconds": age_secs,
                "age_human": age_human,
                "is_stale": is_stale,
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
    include_rotated: bool = False,
    now: Optional[datetime] = None,
    max_screenshot_age_hours: Optional[float] = None,
) -> Dict[str, Any]:
    p = paths or get_leagueloop_paths()
    errors_info = inspect_error_log(p["error_log"], max_lines=max_lines, include_rotated=include_rotated)
    crashes_info = inspect_crash_log(p["crash_log"], max_sessions=max_sessions)
    session_info = inspect_session_log(p["session_log"], max_entries=max_lines)
    fallback_dir = p.get("fallback_screenshots")
    screenshots_info = inspect_screenshots(
        p["screenshots"],
        max_count=max_screenshots,
        fallback_path=fallback_dir,
        now=now,
        max_age_hours=max_screenshot_age_hours,
    )
    debug_path = p.get("debug_log", p["base"] / "logs" / "debug.log")
    debug_info = inspect_debug_log(debug_path, max_lines=max_lines)

    category_counts: Dict[str, int] = {}
    corrupted_count = 0
    stale_count = 0
    used_fallback = any(c.get("source") == "fallback" for c in screenshots_info)
    for c in screenshots_info:
        cat = c.get("category", "general_ui")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        if c.get("is_corrupted"):
            corrupted_count += 1
        if c.get("is_stale"):
            stale_count += 1

    newest_age_sec = screenshots_info[0].get("age_seconds") if screenshots_info and "age_seconds" in screenshots_info[0] else None
    newest_age_hum = screenshots_info[0].get("age_human") if screenshots_info and "age_human" in screenshots_info[0] else None

    screenshot_meta = {
        "captures": screenshots_info,
        "total_returned": len(screenshots_info),
        "source_directory": str(fallback_dir if used_fallback else p["screenshots"]),
        "used_fallback": used_fallback,
        "category_counts": category_counts,
        "corrupted_count": corrupted_count,
        "stale_count": stale_count,
        "all_intact": (corrupted_count == 0),
        "newest_age_seconds": newest_age_sec,
        "newest_age_human": newest_age_hum,
    }

    healthy = (
        len(errors_info.get("recent_errors", [])) == 0
        and errors_info.get("network_throttles_count", 0) == 0
        and not any(e.get("level") in ("ERROR", "CRITICAL") for e in session_info.get("recent_anomalies_or_throttles", []))
        and corrupted_count == 0
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "healthy": healthy,
        "logs_path": str(p["logs"]),
        "screenshots_path": str(p["screenshots"]),
        "fallback_screenshots_path": str(fallback_dir) if fallback_dir else "",
        "error_analysis": errors_info,
        "crash_analysis": crashes_info,
        "session_analysis": session_info,
        "debug_analysis": debug_info,
        "screenshot_analysis": screenshot_meta,
        "recent_screenshots": screenshots_info,
    }


def main():
    parser = argparse.ArgumentParser(description="LeagueLoop Automated Diagnostics")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--summary", action="store_true", default=True, help="Print human-readable summary")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose execution and debug context")
    parser.add_argument("--include-rotated", action="store_true", help="Include rotated log files (error.log.1) if error.log is truncated")
    parser.add_argument("--max-lines", "--lines", "-n", type=int, default=30, help="Number of error.log lines to inspect (default: 30)")
    parser.add_argument("--max-sessions", type=int, default=5, help="Number of crash sessions to inspect (default: 5)")
    parser.add_argument("--max-screenshots", type=int, default=5, help="Number of screenshots to inspect (default: 5)")
    parser.add_argument("--max-screenshot-age-hours", type=float, default=None, help="Maximum allowed age of screenshots in hours before flagging as stale")
    parser.add_argument("--fallback-screenshots", type=str, default=None, help="Custom fallback screenshots directory path")
    args = parser.parse_args()

    paths = get_leagueloop_paths()
    if args.fallback_screenshots:
        paths["fallback_screenshots"] = Path(args.fallback_screenshots)

    diag = run_diagnostics(
        paths=paths,
        max_lines=args.max_lines,
        max_sessions=args.max_sessions,
        max_screenshots=args.max_screenshots,
        include_rotated=args.include_rotated,
        max_screenshot_age_hours=args.max_screenshot_age_hours,
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

    da = diag.get("debug_analysis", {})
    if args.verbose and da.get("exists"):
        print(f"\n[Debug Log Execution Context]")
        print(f"  Total Debug Lines: {da.get('total_lines_inspected', 0)}")
        print(f"  Levels (tail): {da.get('level_counts', {})}")
        print(f"  Diagnostic Tags (tail): {da.get('diagnostic_tags_count', 0)}")
        for d in da.get("recent_diagnostics", [])[:5]:
            print(f"    - {d}")

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

    sa_screens = diag.get("screenshot_analysis", {})
    fallback_note = " (Desktop fallback)" if sa_screens.get("used_fallback") else ""
    categories_str = f" {sa_screens.get('category_counts', {})}" if sa_screens.get('category_counts') else ""
    integrity_str = f" [{sa_screens.get('corrupted_count', 0)} corrupted]" if sa_screens.get("corrupted_count", 0) > 0 else " [all intact]"
    newest_age_str = f" (newest: {sa_screens.get('newest_age_human')})" if sa_screens.get("newest_age_human") else ""
    stale_str = f" [{sa_screens.get('stale_count', 0)} stale]" if sa_screens.get("stale_count", 0) > 0 else ""
    print(f"\n[Screenshots Inspection]")
    print(f"  Recent Captures: {len(diag['recent_screenshots'])}{fallback_note}{categories_str}{integrity_str}{stale_str}{newest_age_str}")
    for s in diag["recent_screenshots"]:
        cat_tag = f"[{s.get('category', 'ui')}] " if s.get("category") else ""
        corrupted_tag = " [CORRUPTED/EMPTY]" if s.get("is_corrupted") else ""
        stale_tag = " [STALE]" if s.get("is_stale") else ""
        age_str = f" - {s.get('age_human')}" if s.get("age_human") else ""
        print(f"    - {cat_tag}{s.get('filename')} ({s.get('modified', '')}{age_str}){corrupted_tag}{stale_tag}")

    sys.exit(0 if diag["healthy"] else 1)


if __name__ == "__main__":
    main()
