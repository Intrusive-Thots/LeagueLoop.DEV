"""
__main__ — Entry point for  py -m self_improving

Orchestrates the autonomous self-improvement loop:
  1. Scan the repository
  2. Run the test suite
  3. Detect regressions against baseline
  4. Run static analyzers
  5. Record findings to persistent memory
  6. Print a human-readable report
  7. Optionally repeat on a schedule
"""

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid cp1252 encoding errors
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from . import repo_index
from . import test_runner
from . import analyzers
from .memory import MemoryStore

# -- Defaults ----------------------------------------------------------

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
STATE_DIR = os.path.join(PROJECT_ROOT, ".agents", "memory")
INDEX_CACHE = os.path.join(STATE_DIR, "repo_index.json")


def _banner(text: str) -> None:
    width = 60
    print()
    print("=" * width)
    print(f"  {text}")
    print("=" * width)


def _section(text: str) -> None:
    print(f"\n-- {text} {'-' * max(1, 50 - len(text))}")


def run_cycle(
    project_root: str = PROJECT_ROOT,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Execute a single improvement cycle. Returns a summary dict."""

    cycle_start = time.perf_counter()
    now = datetime.now(timezone.utc)
    mem = MemoryStore(project_root)

    _banner(f"Self-Improving Loop — {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # ── Phase 1: Load previous state ────────────────────────────────
    _section("Phase 1 · Loading memory")
    loop_state = mem.load_loop_state()
    run_number = loop_state.get("run_number", 0) + 1
    baseline_tests = loop_state.get("test_baseline", None)
    baseline_index = loop_state.get("index_baseline", None)
    print(f"  Run #{run_number}  (baseline: {'exists' if baseline_tests else 'none'})")

    # ── Phase 2: Repository scan ────────────────────────────────────
    _section("Phase 2 · Scanning repository")
    src_root = os.path.join(project_root, "src")
    idx = repo_index.scan_repository(project_root)
    repo_index.save_index(idx, INDEX_CACHE)
    print(f"  {idx['total_files']} files  |  {idx['total_py_lines']} Python lines  |  {idx['scan_time_sec']}s")
    print(f"  Extensions: {json.dumps(idx['ext_counts'])}")
    print(f"  TODOs found: {len(idx['todos'])}")
    print(f"  Missing docstrings: {len(idx['missing_docstrings'])}")

    # Detect repo drift since last run
    if baseline_index:
        line_delta = idx["total_py_lines"] - baseline_index.get("total_py_lines", 0)
        file_delta = idx["total_files"] - baseline_index.get("total_files", 0)
        if line_delta != 0 or file_delta != 0:
            print(f"  Δ since last run: {file_delta:+d} files, {line_delta:+d} lines")

    # ── Phase 3: Run tests ──────────────────────────────────────────
    _section("Phase 3 · Running tests")
    venv = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
    test_results = test_runner.run_tests(project_root, venv_python=venv)
    print(f"  Passed: {test_results['passed']}  Failed: {test_results['failed']}  "
          f"Errors: {test_results['errors']}  Skipped: {test_results['skipped']}  "
          f"({test_results['duration_sec']}s)")

    if test_results["exit_code"] != 0 and verbose:
        print(f"  Exit code: {test_results['exit_code']}")
        if test_results["failures"]:
            for f in test_results["failures"][:5]:
                print(f"    ✗ {f['test']}")

    # ── Phase 4: Detect regressions ─────────────────────────────────
    regressions = test_runner.detect_regressions(test_results, baseline_tests)
    if regressions:
        _section("Phase 4 · ⚠ REGRESSIONS DETECTED")
        for r in regressions:
            print(f"  ⚠ {r}")
    else:
        _section("Phase 4 · No regressions ✓")

    # ── Phase 5: Static analysis ────────────────────────────────────
    _section("Phase 5 · Running analyzers")
    findings = analyzers.run_all_analyzers(idx, test_results, project_root)

    high = [f for f in findings if f.get("severity") == "high"]
    med  = [f for f in findings if f.get("severity") == "medium"]
    low  = [f for f in findings if f.get("severity") == "low"]
    print(f"  Findings: {len(high)} high, {len(med)} medium, {len(low)} low")

    if verbose:
        for f in high + med[:5]:
            print(f"    [{f['severity'].upper()}] {f['message']}")

    # ── Phase 6: Top 5 largest files ────────────────────────────────
    _section("Phase 6 · Complexity hotspots (top 5)")
    for mod in idx["python_modules"][:5]:
        bar = "█" * min(50, mod["lines"] // 30)
        print(f"  {mod['lines']:>5} lines  {bar}  {mod['path']}")

    # ── Phase 7: Persist to memory ──────────────────────────────────
    _section("Phase 7 · Updating memory")
    cycle_duration = round(time.perf_counter() - cycle_start, 3)

    if not dry_run:
        # Save episodic entry
        mem.append_episodic({
            "task": "self_improving_loop",
            "run_number": run_number,
            "duration_seconds": cycle_duration,
            "test_results": {
                "passed": test_results["passed"],
                "failed": test_results["failed"],
                "errors": test_results["errors"],
                "total": test_results["total"],
            },
            "findings_count": {"high": len(high), "medium": len(med), "low": len(low)},
            "regressions": regressions,
            "repo_stats": {
                "total_files": idx["total_files"],
                "total_py_lines": idx["total_py_lines"],
                "todos": len(idx["todos"]),
            },
        })

        # Record any new regressions as failures
        for r in regressions:
            mem.append_failure({
                "error_pattern": f"Regression detected by self_improving loop run #{run_number}",
                "fix": "Investigate the test failures reported above.",
                "context": r,
            })

        # Update global metrics
        mem.update_global_metrics({
            "source": "self_improving_loop",
            "run_number": run_number,
            "runtime_seconds": cycle_duration,
            "tests_passed": test_results["passed"],
            "tests_failed": test_results["failed"],
            "findings_high": len(high),
            "findings_medium": len(med),
            "findings_low": len(low),
            "total_py_lines": idx["total_py_lines"],
        })

        # Persist loop state for next run
        mem.save_loop_state({
            "run_number": run_number,
            "last_run": now.isoformat(),
            "test_baseline": {
                "passed": test_results["passed"],
                "failed": test_results["failed"],
                "errors": test_results["errors"],
            },
            "index_baseline": {
                "total_files": idx["total_files"],
                "total_py_lines": idx["total_py_lines"],
            },
        })
        print(f"  ✓ Memory updated (run #{run_number})")
    else:
        print("  [DRY RUN] Skipping memory writes")

    # ── Summary ─────────────────────────────────────────────────────
    _banner(f"Cycle #{run_number} complete — {cycle_duration}s")

    summary = {
        "run_number": run_number,
        "timestamp": now.isoformat(),
        "duration_sec": cycle_duration,
        "tests": {
            "passed": test_results["passed"],
            "failed": test_results["failed"],
            "errors": test_results["errors"],
            "total": test_results["total"],
        },
        "findings": {"high": len(high), "medium": len(med), "low": len(low)},
        "regressions": regressions,
        "repo": {
            "files": idx["total_files"],
            "py_lines": idx["total_py_lines"],
            "todos": len(idx["todos"]),
        },
    }

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="self_improving",
        description="Autonomous self-improvement loop for LeagueLoop",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single cycle and exit",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run analysis but do not write to memory files",
    )
    parser.add_argument(
        "--interval", type=int, default=60,
        help="Minutes between cycles (default: 60)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print detailed output",
    )
    parser.add_argument(
        "--project", type=str, default=PROJECT_ROOT,
        help=f"Project root directory (default: {PROJECT_ROOT})",
    )

    args = parser.parse_args()

    if args.once:
        summary = run_cycle(
            project_root=args.project,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        sys.exit(0 if not summary["regressions"] else 1)

    # ── Recurring loop ──────────────────────────────────────────────
    print(f"Starting self-improving loop (interval: {args.interval} min)")
    print(f"Project: {args.project}")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            summary = run_cycle(
                project_root=args.project,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )
            next_run = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            print(f"\n⏳ Next cycle in {args.interval} minutes (sleeping until ~{next_run})...")
            time.sleep(args.interval * 60)
        except KeyboardInterrupt:
            print("\n\n🛑 Loop stopped by user.")
            break
        except Exception as e:
            print(f"\n❌ Cycle failed: {e}")
            print(f"  Retrying in {args.interval} minutes...")
            time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
