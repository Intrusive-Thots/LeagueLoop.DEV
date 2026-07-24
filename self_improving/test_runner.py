"""
test_runner.py — Runs pytest suite and tracks test baselines & regressions for self_improving module.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def run_tests(project_root: str, venv_python: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute pytest using subprocess and parse test execution metrics.
    Returns structured results dictionary.
    """
    python_bin = venv_python if (venv_python and os.path.exists(venv_python)) else sys.executable
    cmd = [python_bin, "-m", "pytest", "--tb=short", "-q"]

    start_time = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
        duration = round(time.perf_counter() - start_time, 3)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = proc.returncode

        # Parse test outcomes from pytest short summary
        passed = 0
        failed = 0
        errors = 0
        skipped = 0
        failures = []

        for line in stdout.splitlines():
            line_str = line.strip()
            if "passed" in line_str or "failed" in line_str or "error" in line_str or "skipped" in line_str:
                parts = line_str.split(",")
                for part in parts:
                    part_clean = part.strip()
                    if "passed" in part_clean:
                        try:
                            passed = int(part_clean.split()[0])
                        except (IndexError, ValueError):
                            pass
                    elif "failed" in part_clean:
                        try:
                            failed = int(part_clean.split()[0])
                        except (IndexError, ValueError):
                            pass
                    elif "error" in part_clean:
                        try:
                            errors = int(part_clean.split()[0])
                        except (IndexError, ValueError):
                            pass
                    elif "skipped" in part_clean:
                        try:
                            skipped = int(part_clean.split()[0])
                        except (IndexError, ValueError):
                            pass

            if line_str.startswith("FAILED ") or line_str.startswith("ERROR "):
                test_name = line_str.split()[1] if len(line_str.split()) > 1 else line_str
                failures.append({"test": test_name, "line": line_str})

        total = passed + failed + errors + skipped

        return {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "total": total,
            "duration_sec": duration,
            "exit_code": exit_code,
            "failures": failures,
            "raw_output": stdout,
        }
    except Exception as exc:
        duration = round(time.perf_counter() - start_time, 3)
        return {
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "skipped": 0,
            "total": 0,
            "duration_sec": duration,
            "exit_code": -1,
            "failures": [{"test": "pytest_execution", "line": str(exc)}],
            "raw_output": str(exc),
        }


def detect_regressions(current_results: Dict[str, Any], baseline_results: Optional[Dict[str, Any]]) -> List[str]:
    """
    Compare current test results against baseline to identify regressions.
    """
    if not baseline_results:
        return []

    regressions = []

    prev_passed = baseline_results.get("passed", 0)
    curr_passed = current_results.get("passed", 0)
    if curr_passed < prev_passed:
        regressions.append(f"Passed test count dropped from {prev_passed} to {curr_passed}")

    curr_failed = current_results.get("failed", 0)
    prev_failed = baseline_results.get("failed", 0)
    if curr_failed > prev_failed:
        regressions.append(f"Failed test count increased from {prev_failed} to {curr_failed}")

    curr_errors = current_results.get("errors", 0)
    prev_errors = baseline_results.get("errors", 0)
    if curr_errors > prev_errors:
        regressions.append(f"Test error count increased from {prev_errors} to {curr_errors}")

    return regressions
