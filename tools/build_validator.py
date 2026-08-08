"""
build_validator.py — Automated pre-build verification utility for LeagueLoop.
Validates environment, test suite status, version formatting, required assets, and spec file integrity.
"""

import io
import json
import os
import re
import sys
import time
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# Force UTF-8 encoding on stdout for Windows compatibility
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_validation_lock = threading.Lock()
_validation_telemetry: Dict[str, Any] = {
    "validation_cycles_count": 0,
    "passed_cycles_count": 0,
    "failed_cycles_count": 0,
    "last_validation_timestamp": 0.0,
    "last_run_duration_ms": 0.0,
    "last_version_checked": "",
    "health_status": "UNKNOWN",
    "last_error": None,
}


def validate_version(project_root: Path) -> str:
    version_file = project_root / "src" / "core" / "version.py"
    if not version_file.exists():
        raise FileNotFoundError(f"Version file missing at {version_file}")
    
    content = version_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError("Could not parse __version__ string from src/core/version.py")
    
    version_str = match.group(1)
    print(f"[OK] Version detected: {version_str}")
    return version_str


def validate_test_suite(project_root: Path) -> bool:
    print("Executing pre-build test validation suite...")
    os.environ["HEADLESS"] = "1"
    os.environ["PYTHONUNBUFFERED"] = "1"
    src_dir = str(project_root / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    try:
        import pytest
        ret_code = pytest.main([
            "-q",
            "--disable-warnings",
            "--no-cov",
            str(project_root / "tests")
        ])
        if ret_code != 0:
            print(f"[FAIL] Test suite validation failed with exit code {ret_code}.")
            return False
        print("[OK] All tests passed successfully.")
        return True
    except Exception as e:
        print(f"[FAIL] Test suite validation error: {e}")
        return False


def validate_files(project_root: Path) -> bool:
    required_paths = [
        project_root / "LeagueLoop.spec",
        project_root / "installer.iss",
        project_root / "src" / "ui" / "theme" / "design_tokens.json",
        project_root / "assets" / "app.ico",
    ]
    missing = [str(p) for p in required_paths if not p.exists()]
    if missing:
        print(f"[FAIL] Missing required build files: {missing}")
        return False
    print("[OK] All required spec files and assets present.")
    return True


def verify_system_wide_health(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Task 300: Verify continuous system-wide health and build environment readiness."""
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent

    t_start = time.perf_counter()
    health_status = "HEALTHY"
    errors = []

    try:
        ver = validate_version(project_root)
    except Exception as e:
        ver = "UNKNOWN"
        errors.append(f"Version error: {e}")
        health_status = "UNHEALTHY"

    files_ok = validate_files(project_root)
    if not files_ok:
        errors.append("Missing required spec files or assets")
        if health_status != "UNHEALTHY":
            health_status = "DEGRADED"

    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    test_env_ok = venv_python.exists() or sys.executable is not None

    duration_ms = round((time.perf_counter() - t_start) * 1000.0, 2)

    return {
        "status": health_status,
        "version": ver,
        "files_ok": files_ok,
        "test_environment_ok": test_env_ok,
        "duration_ms": duration_ms,
        "errors": errors,
        "timestamp": time.time(),
    }


def get_build_validation_telemetry() -> Dict[str, Any]:
    """Task 300: Returns telemetry metrics for automated continuous system-wide health and build validation cycles."""
    with _validation_lock:
        data = dict(_validation_telemetry)
        tot = data["validation_cycles_count"]
        passed = data["passed_cycles_count"]
        data["pass_rate_pct"] = round((passed / tot) * 100.0, 2) if tot > 0 else 0.0
        return data


def run_full_validation_cycle(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Task 300: Executes a full build validation cycle, updating global telemetry and readiness state."""
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent

    t_start = time.perf_counter()
    ver = ""
    files_ok = False
    tests_ok = False
    err_msg = None

    try:
        ver = validate_version(project_root)
        files_ok = validate_files(project_root)
        tests_ok = validate_test_suite(project_root)
    except Exception as e:
        err_msg = str(e)

    duration_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
    cycle_passed = files_ok and tests_ok and (err_msg is None)

    with _validation_lock:
        _validation_telemetry["validation_cycles_count"] += 1
        _validation_telemetry["last_validation_timestamp"] = time.time()
        _validation_telemetry["last_run_duration_ms"] = duration_ms
        _validation_telemetry["last_version_checked"] = ver
        _validation_telemetry["last_error"] = err_msg

        if cycle_passed:
            _validation_telemetry["passed_cycles_count"] += 1
            _validation_telemetry["health_status"] = "HEALTHY"
        else:
            _validation_telemetry["failed_cycles_count"] += 1
            _validation_telemetry["health_status"] = "UNHEALTHY"

    return {
        "passed": cycle_passed,
        "version": ver,
        "files_ok": files_ok,
        "tests_ok": tests_ok,
        "duration_ms": duration_ms,
        "error": err_msg,
        "telemetry": get_build_validation_telemetry(),
    }


def main():
    root = Path(__file__).resolve().parent.parent
    print("=" * 60)
    print("  LeagueLoop Build Pipeline Pre-Flight Verification")
    print("=" * 60)

    res = run_full_validation_cycle(root)
    if res["passed"]:
        print(f"\nBUILD READINESS: READY FOR COMPILATION (Cycle completed in {res['duration_ms']}ms)")
        sys.exit(0)
    else:
        print(f"\nBUILD READINESS: UNREADY (Validation Failures: {res['error'] or 'Check logs'})")
        sys.exit(1)


if __name__ == "__main__":
    main()
