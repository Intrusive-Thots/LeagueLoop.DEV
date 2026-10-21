"""
build_validator.py — Automated pre-build verification utility for LeagueLoop.
Validates environment, test suite status, version formatting, required assets, version alignment, and spec file integrity.
"""

import os
import re
import sys
import time
import json
import argparse
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union

# Force UTF-8 encoding on stdout for Windows compatibility
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


def validate_version(project_root: Union[str, Path]) -> str:
    root_path = Path(project_root) if isinstance(project_root, str) else project_root
    version_file = root_path / "src" / "core" / "version.py"
    if not version_file.exists():
        raise FileNotFoundError(f"Version file missing at {version_file}")
    
    content = version_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError("Could not parse __version__ string from src/core/version.py")
    
    version_str = match.group(1)
    print(f"[OK] Version detected: {version_str}")
    return version_str


def validate_version_alignment(project_root: Union[str, Path]) -> Tuple[bool, str]:
    """Validates that src/core/version.py and installer.iss are strictly aligned."""
    root_path = Path(project_root) if isinstance(project_root, str) else project_root
    if str(root_path) not in sys.path:
        sys.path.insert(0, str(root_path))

    version_file = root_path / "src" / "core" / "version.py"
    iss_file = root_path / "installer.iss"
    if not iss_file.exists():
        iss_file = root_path / "build_scripts" / "installer.iss"

    try:
        from tools.bump_version import check_version_alignment
        ok, msg = check_version_alignment(str(version_file), str(iss_file))
        if ok:
            print(f"[OK] Version alignment verified: {msg}")
        else:
            print(f"[FAIL] Version alignment mismatch: {msg}")
        return ok, msg
    except Exception as e:
        msg = f"Version alignment check error: {e}"
        print(f"[FAIL] {msg}")
        return False, msg


def validate_test_suite(project_root: Union[str, Path]) -> bool:
    root_path = Path(project_root) if isinstance(project_root, str) else project_root
    print("Executing pre-build test validation suite...")
    os.environ["HEADLESS"] = "1"
    os.environ["PYTHONUNBUFFERED"] = "1"
    src_dir = str(root_path / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    try:
        import pytest
        ret_code = pytest.main([
            "-q",
            "--disable-warnings",
            "--no-cov",
            str(root_path / "tests")
        ])
        if ret_code != 0:
            print(f"[FAIL] Test suite validation failed with exit code {ret_code}.")
            return False
        print("[OK] All tests passed successfully.")
        return True
    except Exception as e:
        print(f"[FAIL] Test suite validation error: {e}")
        return False


def validate_files(project_root: Union[str, Path]) -> bool:
    root_path = Path(project_root) if isinstance(project_root, str) else project_root
    spec_path = root_path / "LeagueLoop.spec"
    if not spec_path.exists():
        spec_path = root_path / "build_scripts" / "LeagueLoop.spec"

    iss_path = root_path / "installer.iss"
    if not iss_path.exists():
        iss_path = root_path / "build_scripts" / "installer.iss"

    required_paths = [
        spec_path,
        iss_path,
        root_path / "src" / "ui" / "theme" / "design_tokens.json",
        root_path / "assets" / "app.ico",
    ]
    missing = [str(p) for p in required_paths if not p.exists()]
    if missing:
        print(f"[FAIL] Missing required build files: {missing}")
        return False
    print("[OK] All required spec files and assets present.")
    return True


def verify_system_wide_health(project_root: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Task 300: Verify continuous system-wide health and build environment readiness."""
    if project_root is None:
        project_root = PROJECT_ROOT
    elif isinstance(project_root, str):
        project_root = Path(project_root)

    t_start = time.perf_counter()
    health_status = "HEALTHY"
    errors = []

    try:
        ver = validate_version(project_root)
    except Exception as e:
        ver = "UNKNOWN"
        errors.append(f"Version error: {e}")
        health_status = "UNHEALTHY"

    align_ok, align_msg = validate_version_alignment(project_root)
    if not align_ok:
        errors.append(f"Version alignment error: {align_msg}")
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
        "version_aligned": align_ok,
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


def run_full_validation_cycle(project_root: Optional[Union[str, Path]] = None, skip_tests: bool = False) -> Dict[str, Any]:
    """Task 300: Executes a full build validation cycle, updating global telemetry and readiness state."""
    if project_root is None:
        project_root = PROJECT_ROOT
    elif isinstance(project_root, str):
        project_root = Path(project_root)

    t_start = time.perf_counter()
    ver = ""
    files_ok = False
    tests_ok = False
    align_ok = False
    err_msg = None

    try:
        ver = validate_version(project_root)
        align_ok, align_msg = validate_version_alignment(project_root)
        if not align_ok:
            err_msg = align_msg
        files_ok = validate_files(project_root)
        if skip_tests:
            tests_ok = True
        else:
            tests_ok = validate_test_suite(project_root)
    except Exception as e:
        err_msg = str(e)

    duration_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
    cycle_passed = align_ok and files_ok and tests_ok and (err_msg is None)

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
        "version_aligned": align_ok,
        "files_ok": files_ok,
        "tests_ok": tests_ok,
        "duration_ms": duration_ms,
        "error": err_msg,
        "telemetry": get_build_validation_telemetry(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="LeagueLoop Build Pipeline Pre-Flight Verification")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running pytest suite")
    parser.add_argument("--alignment-only", action="store_true", help="Only validate version and alignment")
    parser.add_argument("--health", "--preflight", action="store_true", help="Run fast system-wide health and build environment preflight without running tests")
    parser.add_argument("--telemetry", action="store_true", help="Output build validation telemetry metrics")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args(argv)

    root = PROJECT_ROOT

    if args.health:
        res = verify_system_wide_health(root)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            status_tag = f"[{res['status']}]"
            print(f"Build System Health: {status_tag} (Version: {res.get('version', 'N/A')}, Duration: {res.get('duration_ms', 0)}ms)")
            if res.get("errors"):
                for err in res["errors"]:
                    print(f"  - {err}")
        sys.exit(0 if res["status"] == "HEALTHY" else 1)
        return

    if args.telemetry:
        tel = get_build_validation_telemetry()
        if args.json:
            print(json.dumps(tel, indent=2))
        else:
            print(f"Build Telemetry: cycles={tel.get('validation_cycles_count', 0)}, pass_rate={tel.get('pass_rate_pct', 0.0)}%, health={tel.get('health_status', 'UNKNOWN')}")
        sys.exit(0)
        return

    if args.alignment_only:
        ok, msg = validate_version_alignment(root)
        if args.json:
            print(json.dumps({"version_aligned": ok, "message": msg}, indent=2))
        else:
            print(f"Alignment: {'[ALIGNED]' if ok else '[MISALIGNED]'} - {msg}")
        sys.exit(0 if ok else 1)
        return

    if not args.json:
        print("=" * 60)
        print("  LeagueLoop Build Pipeline Pre-Flight Verification")
        print("=" * 60)

    res = run_full_validation_cycle(root, skip_tests=args.skip_tests)

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        if res["passed"]:
            print(f"\nBUILD READINESS: READY FOR COMPILATION (Cycle completed in {res['duration_ms']}ms)")
        else:
            print(f"\nBUILD READINESS: UNREADY (Validation Failures: {res['error'] or 'Check logs'})")

    sys.exit(0 if res["passed"] else 1)
    return


if __name__ == "__main__":
    main()
