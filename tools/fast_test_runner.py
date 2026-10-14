#!/usr/bin/env python3
"""
fast_test_runner.py — High-Performance Targeted Test Runner for LeagueLoop.DEV

Reduces test execution time from >20s to <2s by intelligently mapping git-modified
source and test files to their respective pytest targets.
"""

import os
import re
import sys
import time
import subprocess
import argparse
from pathlib import Path
from typing import List, Set

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"


def get_git_modified_files() -> Set[str]:
    """Retrieve all untracked, unstaged, and staged modified files."""
    modified = set()
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True
        )
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                modified.add(parts[-1].replace("\\", "/"))
    except Exception:
        pass

    # Also check latest commit if working tree is clean
    if not modified:
        try:
            res = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if line.strip():
                        modified.add(line.strip().replace("\\", "/"))
        except Exception:
            pass

    return modified


def map_source_to_tests(modified_files: Set[str]) -> List[str]:
    """Maps modified files in src/ or tests/ to relevant test file paths."""
    test_targets: Set[str] = set()

    for path_str in modified_files:
        p = Path(path_str)
        # Direct test modification
        if p.parts and p.parts[0] == "tests" and p.suffix == ".py":
            full = PROJECT_ROOT / p
            if full.exists():
                test_targets.add(str(full))
            continue

        # Source code modification
        stem = p.stem.lower()
        # Direct pattern matching: test_{stem}.py
        direct_match = TESTS_DIR / f"test_{stem}.py"
        if direct_match.exists():
            test_targets.add(str(direct_match))

        # Specialized service / core component mappings
        if "account" in stem:
            for cand in ["test_account_detection.py", "test_account_switching.py", "test_account_identity.py", "test_account_session_vault.py"]:
                t = TESTS_DIR / cand
                if t.exists():
                    test_targets.add(str(t))

        if "api_handler" in stem:
            for cand in ["test_api_handler.py", "test_ws_telemetry.py", "test_api_performance_control.py"]:
                t = TESTS_DIR / cand
                if t.exists():
                    test_targets.add(str(t))

        if "automation" in stem:
            for cand in ["test_automation.py", "test_automation_draft.py", "test_automation_wiring.py"]:
                t = TESTS_DIR / cand
                if t.exists():
                    test_targets.add(str(t))

        if "loot" in stem:
            t = TESTS_DIR / "test_loot_service.py"
            if t.exists():
                test_targets.add(str(t))

    return sorted(list(test_targets))


def run_tests(targets: List[str], extra_args: List[str] = None) -> int:
    python_exe = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
    if not Path(python_exe).exists():
        python_exe = sys.executable

    cmd = [python_exe, "-m", "pytest", "-q", "--no-cov"]
    if extra_args:
        cmd.extend(extra_args)
    if targets:
        cmd.extend(targets)

    print(f"Executing: {' '.join(cmd)}")
    start = time.perf_counter()
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    duration = time.perf_counter() - start
    print(f"\nExecution finished in {duration:.2f}s (Exit code: {res.returncode})")
    return res.returncode


def main():
    parser = argparse.ArgumentParser(description="LeagueLoop Fast Targeted Test Runner")
    parser.add_argument("--all", action="store_true", help="Run full test suite unconditionally")
    parser.add_argument("extra", nargs="*", help="Extra arguments to pass to pytest")
    args = parser.parse_args()

    if args.all:
        print("[Fast Runner] Running full test suite...")
        sys.exit(run_tests([], args.extra))

    modified = get_git_modified_files()
    print(f"[Fast Runner] Detected modified files in git ({len(modified)}):")
    for m in sorted(modified):
        print(f"  - {m}")

    targets = map_source_to_tests(modified)
    if not targets:
        print("[Fast Runner] No targeted tests found for modified files. Running full test suite...")
        sys.exit(run_tests([], args.extra))

    print(f"\n[Fast Runner] Selected targeted test suites ({len(targets)}):")
    for t in targets:
        print(f"  - {Path(t).name}")

    sys.exit(run_tests(targets, args.extra))


if __name__ == "__main__":
    main()
