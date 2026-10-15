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
        "sessions": base / "sessions",
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
    default_stats = {"count": 0, "min_ms": None, "max_ms": None, "avg_ms": None}
    result: Dict[str, Any] = {
        "exists": path.exists(),
        "total_entries": 0,
        "recent_entries": [],
        "level_counts": {},
        "active_sessions": [],
        "recent_anomalies_or_throttles": [],
        "stability": {
            "rating": "EXCELLENT",
            "connection_drops_count": 0,
            "drop_reasons": [],
            "throttle_events_count": 0,
            "latency_stats": dict(default_stats),
        },
        "latency_stats": dict(default_stats),
        "connection_drops": [],
        "throttle_events": [],
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
        latency_values: List[float] = []
        connection_drops: List[Dict[str, Any]] = []
        throttle_events: List[Dict[str, Any]] = []
        drop_reasons: List[str] = []

        import re
        latency_re = re.compile(r"Latency anomaly detected on event:\s*([\d\.]+)ms", re.IGNORECASE)
        drop_re = re.compile(r"Connection drop recorded:\s*(.*?)(?:\s*\(Total drops:\s*(\d+)\))?$", re.IGNORECASE)
        throttle_re = re.compile(r"Rapid connection drops detected.*?backoff floor=([\d\.]+)s", re.IGNORECASE)

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
                msg = entry.get("msg", "")

                m_lat = latency_re.search(msg)
                if m_lat:
                    try:
                        latency_values.append(float(m_lat.group(1)))
                    except ValueError:
                        pass

                if tag == "LCU_DIAGNOSTICS" or "Connection drop recorded" in msg:
                    m_drop = drop_re.search(msg)
                    if m_drop:
                        reason = m_drop.group(1).strip()
                        drop_reasons.append(reason)
                        connection_drops.append({
                            "ts": entry.get("ts"),
                            "reason": reason,
                            "total_drops": int(m_drop.group(2)) if m_drop.group(2) else 1,
                        })

                if tag == "LCU_NETWORK_THROTTLE" or "reconnect rate throttling" in msg:
                    m_thr = throttle_re.search(msg)
                    throttle_events.append({
                        "ts": entry.get("ts"),
                        "msg": msg,
                        "backoff_floor": float(m_thr.group(1)) if m_thr else None,
                    })

                if "THROTTLE" in tag or "ANOMALY" in tag or lvl in ("WARNING", "ERROR", "CRITICAL"):
                    anomalies.append({
                        "ts": entry.get("ts"),
                        "level": lvl,
                        "tag": tag,
                        "msg": msg,
                    })
            except Exception:
                continue

        lat_stats = {
            "count": len(latency_values),
            "min_ms": round(min(latency_values), 2) if latency_values else None,
            "max_ms": round(max(latency_values), 2) if latency_values else None,
            "avg_ms": round(sum(latency_values) / len(latency_values), 2) if latency_values else None,
        }

        drop_count = len(connection_drops)
        thr_count = len(throttle_events)
        lat_count = len(latency_values)

        if drop_count == 0 and thr_count == 0 and lat_count == 0:
            rating = "EXCELLENT"
        elif drop_count == 0 and thr_count == 0 and lat_count <= 5:
            rating = "GOOD"
        else:
            rating = "DEGRADED"

        stability_summary = {
            "rating": rating,
            "connection_drops_count": drop_count,
            "drop_reasons": list(dict.fromkeys(drop_reasons)),
            "throttle_events_count": thr_count,
            "latency_stats": lat_stats,
        }

        result["recent_entries"] = parsed_entries
        result["level_counts"] = level_counts
        result["active_sessions"] = sorted(list(sessions_seen))
        result["recent_anomalies_or_throttles"] = anomalies
        result["stability"] = stability_summary
        result["latency_stats"] = lat_stats
        result["connection_drops"] = connection_drops
        result["throttle_events"] = throttle_events
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



def inspect_saved_sessions(
    path: Path,
    max_age_days: Optional[float] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Audits saved multi-account SessionVault slots in %LOCALAPPDATA%\\LeagueLoop\\sessions.

    Each account slot folder should contain:
      - session.json (manifest with account_id and captured_at)
      - RiotClientPrivateSettings.yaml
      - RiotGamesPrivateSettings.yaml
    """
    result: Dict[str, Any] = {
        "exists": path.exists(),
        "total_accounts": 0,
        "healthy_accounts": 0,
        "corrupted_accounts": 0,
        "stale_accounts": 0,
        "accounts": [],
    }
    if not path.exists():
        return result

    ref_now = now or datetime.now()
    ref_ts = ref_now.timestamp()

    try:
        slots = [d for d in path.iterdir() if d.is_dir()]
        result["total_accounts"] = len(slots)

        for slot in sorted(slots, key=lambda d: d.name.lower()):
            account_id = slot.name
            manifest_file = slot / "session.json"
            yaml_client = slot / "RiotClientPrivateSettings.yaml"
            yaml_games = slot / "RiotGamesPrivateSettings.yaml"

            missing_files: List[str] = []
            corrupted_files: List[str] = []
            captured_at: Optional[float] = None

            # Check manifest
            if not manifest_file.exists():
                missing_files.append("session.json")
            else:
                if manifest_file.stat().st_size == 0:
                    corrupted_files.append("session.json (0-byte)")
                else:
                    try:
                        with open(manifest_file, "r", encoding="utf-8", errors="replace") as f:
                            m_data = json.load(f)
                            captured_at = float(m_data.get("captured_at") or 0.0)
                            if m_data.get("account_id"):
                                account_id = m_data["account_id"]
                    except Exception:
                        corrupted_files.append("session.json (invalid JSON)")

            # Check YAML files
            for yf in [yaml_client, yaml_games]:
                if not yf.exists():
                    missing_files.append(yf.name)
                elif yf.stat().st_size == 0:
                    corrupted_files.append(f"{yf.name} (0-byte)")

            # Determine age
            if not captured_at or captured_at <= 0.0:
                try:
                    target_cand = yaml_client if yaml_client.exists() else manifest_file
                    captured_at = target_cand.stat().st_mtime if target_cand.exists() else slot.stat().st_mtime
                except Exception:
                    captured_at = ref_ts

            age_secs = max(0.0, round(ref_ts - captured_at, 1))
            age_days = round(age_secs / 86400.0, 2)
            age_human = format_human_age(age_secs)
            is_stale = bool(max_age_days is not None and age_days > max_age_days)
            is_corrupted = len(corrupted_files) > 0 or len(missing_files) > 0

            acc_info = {
                "account_id": account_id,
                "slot_name": slot.name,
                "is_corrupted": is_corrupted,
                "is_stale": is_stale,
                "age_days": age_days,
                "age_human": age_human,
                "missing_files": missing_files,
                "corrupted_files": corrupted_files,
                "captured_at": captured_at,
            }
            result["accounts"].append(acc_info)

            if is_corrupted:
                result["corrupted_accounts"] += 1
            else:
                result["healthy_accounts"] += 1
            if is_stale:
                result["stale_accounts"] += 1

    except Exception as e:
        result["error_reading"] = str(e)

    return result


def inspect_storage_usage(
    base_path: Path,
    max_logs_mb: float = 100.0,
    max_screenshots_mb: float = 100.0,
) -> Dict[str, Any]:
    """Audits disk footprint across logs, screenshots, and saved sessions in LeagueLoop AppData."""
    result: Dict[str, Any] = {
        "exists": base_path.exists(),
        "total_mb": 0.0,
        "logs": {
            "total_mb": 0.0,
            "active_mb": 0.0,
            "rotated_mb": 0.0,
            "file_count": 0,
            "rotated_file_count": 0,
        },
        "screenshots": {
            "total_mb": 0.0,
            "file_count": 0,
        },
        "sessions": {
            "total_mb": 0.0,
            "slot_count": 0,
        },
        "is_warning": False,
        "warnings": [],
        "status": "OPTIMAL",
    }
    if not base_path.exists():
        return result

    try:
        # Logs
        logs_dir = base_path / "logs"
        if logs_dir.exists():
            active_names = {"error.log", "crash.log", "debug.log", "session.jsonl"}
            for p in logs_dir.glob("*"):
                if p.is_file():
                    sz_mb = p.stat().st_size / (1024 * 1024)
                    result["logs"]["total_mb"] += sz_mb
                    result["logs"]["file_count"] += 1
                    if p.name in active_names:
                        result["logs"]["active_mb"] += sz_mb
                    else:
                        result["logs"]["rotated_mb"] += sz_mb
                        result["logs"]["rotated_file_count"] += 1

        # Screenshots
        sc_dir = base_path / "debug_screenshots"
        if sc_dir.exists():
            for p in sc_dir.glob("*.png"):
                if p.is_file():
                    sz_mb = p.stat().st_size / (1024 * 1024)
                    result["screenshots"]["total_mb"] += sz_mb
                    result["screenshots"]["file_count"] += 1

        # Sessions
        sess_dir = base_path / "sessions"
        if sess_dir.exists():
            slots = [d for d in sess_dir.iterdir() if d.is_dir()]
            result["sessions"]["slot_count"] = len(slots)
            for p in sess_dir.rglob("*"):
                if p.is_file():
                    result["sessions"]["total_mb"] += p.stat().st_size / (1024 * 1024)

        logs_mb_raw = result["logs"]["total_mb"]
        screenshots_mb_raw = result["screenshots"]["total_mb"]

        warnings = []
        if logs_mb_raw > max_logs_mb:
            warnings.append(f"Logs footprint ({round(logs_mb_raw, 2)} MB) exceeds threshold ({max_logs_mb} MB)")
        if screenshots_mb_raw > max_screenshots_mb:
            warnings.append(f"Screenshots footprint ({round(screenshots_mb_raw, 2)} MB) exceeds threshold ({max_screenshots_mb} MB)")

        result["warnings"] = warnings
        result["is_warning"] = len(warnings) > 0
        if result["is_warning"]:
            result["status"] = "WARNING"
        elif (logs_mb_raw + screenshots_mb_raw) > (max_logs_mb + max_screenshots_mb) * 0.5:
            result["status"] = "ELEVATED"
        else:
            result["status"] = "OPTIMAL"

        # Rounding
        result["logs"]["total_mb"] = round(result["logs"]["total_mb"], 2)
        result["logs"]["active_mb"] = round(result["logs"]["active_mb"], 2)
        result["logs"]["rotated_mb"] = round(result["logs"]["rotated_mb"], 2)
        result["screenshots"]["total_mb"] = round(result["screenshots"]["total_mb"], 2)
        result["sessions"]["total_mb"] = round(result["sessions"]["total_mb"], 2)
        result["total_mb"] = round(
            result["logs"]["total_mb"] + result["screenshots"]["total_mb"] + result["sessions"]["total_mb"],
            2,
        )

    except Exception as e:
        result["error_reading"] = str(e)

    return result


def run_diagnostics(
    paths: Optional[Dict[str, Path]] = None,
    max_lines: int = 30,
    max_sessions: int = 5,
    max_screenshots: int = 5,
    include_rotated: bool = False,
    now: Optional[datetime] = None,
    max_screenshot_age_hours: Optional[float] = None,
    max_session_age_days: Optional[float] = None,
    max_logs_mb: float = 100.0,
    max_screenshots_mb: float = 100.0,
    strict_storage: bool = False,
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

    sessions_path = p.get("sessions", p["base"] / "sessions")
    sessions_info = inspect_saved_sessions(sessions_path, max_age_days=max_session_age_days, now=now)
    storage_info = inspect_storage_usage(p["base"], max_logs_mb=max_logs_mb, max_screenshots_mb=max_screenshots_mb)

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
        and sessions_info.get("corrupted_accounts", 0) == 0
        and (not strict_storage or not storage_info.get("is_warning", False))
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "healthy": healthy,
        "logs_path": str(p["logs"]),
        "screenshots_path": str(p["screenshots"]),
        "sessions_path": str(sessions_path),
        "fallback_screenshots_path": str(fallback_dir) if fallback_dir else "",
        "error_analysis": errors_info,
        "crash_analysis": crashes_info,
        "session_analysis": session_info,
        "debug_analysis": debug_info,
        "screenshot_analysis": screenshot_meta,
        "sessions_analysis": sessions_info,
        "storage_analysis": storage_info,
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
    parser.add_argument("--max-session-age-days", type=float, default=None, help="Maximum allowed age of saved Riot account sessions in days before flagging as stale")
    parser.add_argument("--max-logs-mb", type=float, default=100.0, help="Maximum allowed total size of logs in MB before warning (default: 100.0)")
    parser.add_argument("--max-screenshots-mb", type=float, default=100.0, help="Maximum allowed total size of debug screenshots in MB before warning (default: 100.0)")
    parser.add_argument("--strict-storage", action="store_true", help="Treat storage threshold warnings as fatal health failures")
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
        max_session_age_days=args.max_session_age_days,
        max_logs_mb=args.max_logs_mb,
        max_screenshots_mb=args.max_screenshots_mb,
        strict_storage=args.strict_storage,
    )

    if args.json:
        print(json.dumps(diag, indent=2))
        sys.exit(0 if diag["healthy"] else 1)

    print("=== LeagueLoop Diagnostics ===")
    print(f"Status: {'[HEALTHY]' if diag['healthy'] else '[NEEDS ATTENTION]'}")
    print(f"Logs Path: {diag['logs_path']}")
    print(f"Screenshots Path: {diag['screenshots_path']}")
    print(f"Sessions Path: {diag.get('sessions_path', '')}")

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
        stab = sa.get("stability", {})
        if stab:
            print(f"  Network Stability: [{stab.get('rating', 'UNKNOWN')}] (drops: {stab.get('connection_drops_count', 0)}, throttles: {stab.get('throttle_events_count', 0)})")
            lat = stab.get("latency_stats", {})
            if lat.get("count", 0) > 0:
                print(f"  Latency Anomalies (tail): {lat['count']} events (min={lat['min_ms']}ms, avg={lat['avg_ms']}ms, max={lat['max_ms']}ms)")
            if stab.get("drop_reasons"):
                print(f"  Drop Reasons: {stab['drop_reasons']}")
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


    sv = diag.get("sessions_analysis", {})
    if sv.get("exists"):
        corrupted_note = f" [{sv.get('corrupted_accounts', 0)} corrupted]" if sv.get("corrupted_accounts", 0) > 0 else " [all intact]"
        stale_note = f" [{sv.get('stale_accounts', 0)} stale]" if sv.get("stale_accounts", 0) > 0 else ""
        print(f"\n[Saved Sessions Vault]")
        print(f"  Total Account Slots: {sv.get('total_accounts', 0)}{corrupted_note}{stale_note}")
        for acc in sv.get("accounts", []):
            corrupt_tag = " [CORRUPTED]" if acc.get("is_corrupted") else ""
            stale_tag = " [STALE]" if acc.get("is_stale") else ""
            print(f"    - {acc.get('account_id')} ({acc.get('slot_name')}): {acc.get('age_human')}{corrupt_tag}{stale_tag}")
            if acc.get("missing_files"):
                print(f"        missing: {acc.get('missing_files')}")
            if acc.get("corrupted_files"):
                print(f"        corrupted: {acc.get('corrupted_files')}")

    st = diag.get("storage_analysis", {})
    if st.get("exists"):
        print(f"\n[Storage Footprint]")
        print(f"  Total Disk Footprint: {st.get('total_mb', 0.0)} MB (Status: [{st.get('status', 'OPTIMAL')}])")
        logs_st = st.get("logs", {})
        print(f"  Logs: {logs_st.get('total_mb', 0.0)} MB ({logs_st.get('file_count', 0)} files, rotated: {logs_st.get('rotated_mb', 0.0)} MB across {logs_st.get('rotated_file_count', 0)} files)")
        sc_st = st.get("screenshots", {})
        print(f"  Screenshots: {sc_st.get('total_mb', 0.0)} MB ({sc_st.get('file_count', 0)} files)")
        sess_st = st.get("sessions", {})
        print(f"  Sessions: {sess_st.get('total_mb', 0.0)} MB ({sess_st.get('slot_count', 0)} slots)")
        if st.get("warnings"):
            print(f"  Storage Warnings:")
            for w in st.get("warnings", []):
                print(f"    - [WARNING] {w}")

    sys.exit(0 if diag["healthy"] else 1)


if __name__ == "__main__":
    main()
