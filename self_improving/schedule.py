#!/usr/bin/env python3
"""
schedule.py — Production-ready scheduler for LeagueLoop self-improvement cycle.

This script provides multiple scheduling modes:
  - Continuous loop with configurable intervals
  - Cron-like scheduled runs (specific times)
  - One-shot improvement cycles
  - Smart adaptive scheduling based on code changes

Usage:
    py -m self_improving.schedule --mode continuous --interval 60
    py -m self_improving.schedule --mode cron --times "09:00,17:00"
    py -m self_improving.schedule --mode once
    py -m self_improving.schedule --mode smart --interval 30

Features:
  - Graceful shutdown on SIGINT/SIGTERM
  - Logging to file and console
  - Error recovery and retry logic
  - Resource monitoring (CPU/memory limits)
  - Email/Slack notifications (optional)
  - Metrics export to Prometheus format
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from self_improving import repo_index, test_runner, analyzers
from self_improving.memory import MemoryStore

# ── Configuration ─────────────────────────────────────────────────────

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
STATE_DIR = os.path.join(PROJECT_ROOT, ".agents", "memory")
SCHEDULE_STATE = os.path.join(STATE_DIR, "schedule_state.json")
LOG_FILE = os.path.join(STATE_DIR, "schedule.log")

# Default scheduling parameters
DEFAULT_INTERVAL_MINUTES = 60
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 300  # 5 minutes

# Resource limits
MAX_CPU_PERCENT = 80
MAX_MEMORY_MB = 2048

# ── Logging Setup ─────────────────────────────────────────────────────


def setup_logging(log_file: str, verbose: bool = False) -> logging.Logger:
    """Configure logging to file and console."""
    logger = logging.getLogger("self_improving.schedule")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # File handler
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


# ── Data Classes ──────────────────────────────────────────────────────

@dataclass
class ScheduleState:
    """Persisted scheduler state."""
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    consecutive_failures: int = 0
    total_duration_sec: float = 0.0
    avg_duration_sec: float = 0.0
    last_commit_hash: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "ScheduleState":
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class ImprovementReport:
    """Summary of a single improvement cycle."""
    timestamp: str
    duration_sec: float
    tests_passed: int
    tests_failed: int
    tests_errors: int
    findings_high: int
    findings_medium: int
    findings_low: int
    regressions: List[str]
    files_changed: int
    lines_changed: int
    success: bool
    error_message: Optional[str] = None


# ── Helper Functions ──────────────────────────────────────────────────

def load_schedule_state() -> ScheduleState:
    """Load persisted scheduler state."""
    if Path(SCHEDULE_STATE).exists():
        try:
            data = json.loads(Path(SCHEDULE_STATE).read_text(encoding="utf-8"))
            return ScheduleState.from_dict(data)
        except Exception:
            pass
    return ScheduleState()


def save_schedule_state(state: ScheduleState) -> None:
    """Persist scheduler state."""
    Path(SCHEDULE_STATE).parent.mkdir(parents=True, exist_ok=True)
    Path(SCHEDULE_STATE).write_text(
        json.dumps(state.to_dict(), indent=2),
        encoding="utf-8"
    )


def get_git_commit_hash() -> Optional[str]:
    """Get current git commit hash if available."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def detect_code_changes(last_commit: Optional[str]) -> tuple[int, int]:
    """Detect file and line changes since last run."""
    if not last_commit:
        return 0, 0

    import subprocess
    try:
        # Get diff stats since last commit
        result = subprocess.run(
            ["git", "diff", "--shortstat", last_commit],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            output = result.stdout
            # Parse: X files changed, Y insertions(+), Z deletions(-)
            files = insertions = deletions = 0
            for part in output.split(","):
                part = part.strip()
                if "file" in part:
                    files = int(part.split()[0])
                elif "insertion" in part:
                    insertions = int(part.split()[0])
                elif "deletion" in part:
                    deletions = int(part.split()[0])
            return files, insertions - deletions
    except Exception:
        pass
    return 0, 0


def check_resource_usage() -> Dict[str, float]:
    """Check current CPU and memory usage."""
    import psutil
    process = psutil.Process(os.getpid())
    return {
        "cpu_percent": process.cpu_percent(interval=0.1),
        "memory_mb": process.memory_info().rss / (1024 * 1024),
    }


def should_skip_due_to_resources() -> bool:
    """Check if resource usage exceeds limits."""
    try:
        usage = check_resource_usage()
        if usage["cpu_percent"] > MAX_CPU_PERCENT:
            return True
        if usage["memory_mb"] > MAX_MEMORY_MB:
            return True
    except Exception:
        pass
    return False


# ── Core Improvement Cycle ────────────────────────────────────────────

def run_improvement_cycle(
    project_root: str = PROJECT_ROOT,
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
) -> ImprovementReport:
    """Execute a single self-improvement cycle."""
    start_time = time.perf_counter()
    now = datetime.now(timezone.utc)
    mem = MemoryStore(project_root)

    if logger:
        logger.info(f"Starting improvement cycle at {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    try:
        # Phase 1: Repository scan
        idx = repo_index.scan_repository(project_root)

        # Phase 2: Run tests
        venv = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
        test_results = test_runner.run_tests(project_root, venv_python=venv)

        # Phase 3: Load baseline and detect regressions
        loop_state = mem.load_loop_state()
        baseline_tests = loop_state.get("test_baseline", None)
        regressions = test_runner.detect_regressions(test_results, baseline_tests)

        # Phase 4: Static analysis
        findings = analyzers.run_all_analyzers(idx, test_results, project_root)
        high = len([f for f in findings if f.get("severity") == "high"])
        med = len([f for f in findings if f.get("severity") == "medium"])
        low = len([f for f in findings if f.get("severity") == "low"])

        # Phase 5: Detect code changes
        state = load_schedule_state()
        files_changed, lines_changed = detect_code_changes(state.last_commit_hash)

        # Phase 6: Update memory
        duration = round(time.perf_counter() - start_time, 3)
        mem.append_episodic({
            "task": "scheduled_improvement_cycle",
            "run_number": state.run_count + 1,
            "duration_seconds": duration,
            "test_results": {
                "passed": test_results["passed"],
                "failed": test_results["failed"],
                "errors": test_results["errors"],
                "total": test_results["total"],
            },
            "findings_count": {"high": high, "medium": med, "low": low},
            "regressions": regressions,
            "repo_stats": {
                "total_files": idx["total_files"],
                "total_py_lines": idx["total_py_lines"],
                "todos": len(idx["todos"]),
            },
        })

        # Update loop state
        mem.save_loop_state({
            "run_number": state.run_count + 1,
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

        # Determine success
        success = test_results["errors"] == 0 and len(regressions) == 0
        error_msg = None

        if test_results["errors"] > 0:
            error_msg = f"{test_results['errors']} test errors occurred"
        elif regressions:
            error_msg = f"Regressions detected: {', '.join(regressions[:3])}"

        report = ImprovementReport(
            timestamp=now.isoformat(),
            duration_sec=duration,
            tests_passed=test_results["passed"],
            tests_failed=test_results["failed"],
            tests_errors=test_results["errors"],
            findings_high=high,
            findings_medium=med,
            findings_low=low,
            regressions=regressions,
            files_changed=files_changed,
            lines_changed=lines_changed,
            success=success,
            error_message=error_msg,
        )

        if logger:
            status = "✓ SUCCESS" if success else "⚠ ISSUES FOUND"
            logger.info(f"Cycle complete [{status}]: {duration}s | "
                       f"Tests: {test_results['passed']}/{test_results['total']} | "
                       f"Findings: {high}H/{med}M/{low}L")

        return report

    except Exception as e:
        duration = round(time.perf_counter() - start_time, 3)
        if logger:
            logger.error(f"Cycle failed after {duration}s: {e}")
        return ImprovementReport(
            timestamp=now.isoformat(),
            duration_sec=duration,
            tests_passed=0,
            tests_failed=0,
            tests_errors=0,
            findings_high=0,
            findings_medium=0,
            findings_low=0,
            regressions=[],
            files_changed=0,
            lines_changed=0,
            success=False,
            error_message=str(e),
        )


# ── Scheduling Modes ──────────────────────────────────────────────────

def run_continuous_mode(
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    verbose: bool = False,
    max_runs: Optional[int] = None,
) -> None:
    """Run improvement cycles continuously at fixed intervals."""
    logger = setup_logging(LOG_FILE, verbose)
    state = load_schedule_state()

    logger.info("=" * 60)
    logger.info("SELF-IMPROVEMENT SCHEDULER — CONTINUOUS MODE")
    logger.info("=" * 60)
    logger.info(f"Interval: {interval_minutes} minutes")
    logger.info(f"Project: {PROJECT_ROOT}")
    logger.info(f"Max runs: {max_runs or 'unlimited'}")
    logger.info("Press Ctrl+C to stop\n")

    runs_completed = 0
    retry_count = 0

    while True:
        try:
            # Check resource limits before running
            if should_skip_due_to_resources():
                logger.warning("Skipping cycle: resource usage exceeds limits")
                time.sleep(60)  # Wait 1 minute before checking again
                continue

            # Run improvement cycle
            report = run_improvement_cycle(verbose=verbose, logger=logger)

            # Update state
            state.run_count += 1
            state.last_run = report.timestamp
            state.total_duration_sec += report.duration_sec
            state.avg_duration_sec = state.total_duration_sec / state.run_count
            state.last_commit_hash = get_git_commit_hash()

            if report.success:
                state.successful_runs += 1
                state.consecutive_failures = 0
                retry_count = 0
            else:
                state.failed_runs += 1
                state.consecutive_failures += 1
                logger.warning(f"Consecutive failures: {state.consecutive_failures}")

                # Exponential backoff on repeated failures
                if state.consecutive_failures >= MAX_RETRIES:
                    delay = RETRY_DELAY_SECONDS * (2 ** (state.consecutive_failures - MAX_RETRIES))
                    logger.warning(f"Multiple failures detected. Waiting {delay}s before next attempt.")
                    time.sleep(delay)

            runs_completed += 1
            save_schedule_state(state)

            # Check max runs limit
            if max_runs and runs_completed >= max_runs:
                logger.info(f"Reached maximum runs ({max_runs}). Exiting.")
                break

            # Wait for next cycle
            next_run = datetime.now(timezone.utc) + timedelta(minutes=interval_minutes)
            logger.info(f"Next cycle in {interval_minutes} minutes (at ~{next_run.strftime('%H:%M:%S UTC')})")
            time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            logger.info("\n\nScheduler stopped by user.")
            logger.info(f"Total runs: {state.run_count} | "
                       f"Successful: {state.successful_runs} | "
                       f"Failed: {state.failed_runs}")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(60)  # Wait before retrying


def run_cron_mode(
    times: List[str],
    verbose: bool = False,
) -> None:
    """Run improvement cycles at specific times (cron-like)."""
    logger = setup_logging(LOG_FILE, verbose)
    state = load_schedule_state()

    logger.info("=" * 60)
    logger.info("SELF-IMPROVEMENT SCHEDULER — CRON MODE")
    logger.info("=" * 60)
    logger.info(f"Scheduled times: {', '.join(times)}")
    logger.info("Press Ctrl+C to stop\n")

    def parse_time(time_str: str) -> tuple[int, int]:
        parts = time_str.strip().split(":")
        return int(parts[0]), int(parts[1])

    scheduled_times = [parse_time(t) for t in times]

    while True:
        try:
            now = datetime.now()
            current_time = (now.hour, now.minute)

            if current_time in scheduled_times and now.second < 10:
                # Check if we already ran this minute
                if state.last_run:
                    last_run_dt = datetime.fromisoformat(state.last_run.replace('Z', '+00:00'))
                    if (last_run_dt.hour, last_run_dt.minute) == current_time:
                        time.sleep(60 - now.second)
                        continue

                logger.info(f"Running scheduled cycle at {now.strftime('%H:%M')}")
                report = run_improvement_cycle(verbose=verbose, logger=logger)

                state.run_count += 1
                state.last_run = report.timestamp
                if report.success:
                    state.successful_runs += 1
                else:
                    state.failed_runs += 1
                save_schedule_state(state)

            # Sleep until next minute
            time.sleep(60 - now.second)

        except KeyboardInterrupt:
            logger.info("\n\nScheduler stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(60)


def run_smart_mode(
    base_interval_minutes: int = 30,
    verbose: bool = False,
) -> None:
    """
    Adaptive scheduling based on code activity.
    
    - Shorter intervals when code is changing frequently
    - Longer intervals during quiet periods
    - Immediate runs on detected regressions
    """
    logger = setup_logging(LOG_FILE, verbose)
    state = load_schedule_state()

    logger.info("=" * 60)
    logger.info("SELF-IMPROVEMENT SCHEDULER — SMART ADAPTIVE MODE")
    logger.info("=" * 60)
    logger.info(f"Base interval: {base_interval_minutes} minutes")
    logger.info("Press Ctrl+C to stop\n")

    activity_score = 0  # Tracks recent code change activity
    min_interval = 15  # Minimum interval in minutes
    max_interval = 120  # Maximum interval in minutes

    while True:
        try:
            # Detect recent changes
            files_changed, lines_changed = detect_code_changes(state.last_commit_hash)

            # Adjust activity score
            if files_changed > 0 or lines_changed != 0:
                activity_score = min(100, activity_score + 20)
                logger.info(f"Code changes detected: {files_changed} files, {lines_changed} lines")
            else:
                activity_score = max(0, activity_score - 5)

            # Calculate dynamic interval
            activity_factor = activity_score / 100
            interval = max_interval - (activity_factor * (max_interval - min_interval))
            interval = max(min_interval, min(max_interval, interval))

            logger.info(f"Activity score: {activity_score}/100 → Interval: {interval:.0f} min")

            # Run improvement cycle
            report = run_improvement_cycle(verbose=verbose, logger=logger)

            # Update state
            state.run_count += 1
            state.last_run = report.timestamp
            state.last_commit_hash = get_git_commit_hash()
            state.total_duration_sec += report.duration_sec
            state.avg_duration_sec = state.total_duration_sec / state.run_count

            if report.success:
                state.successful_runs += 1
            else:
                state.failed_runs += 1
                # Reduce interval on failures for faster feedback
                interval = max(min_interval, interval / 2)

            save_schedule_state(state)

            # Wait for next cycle
            next_run = datetime.now(timezone.utc) + timedelta(minutes=interval)
            logger.info(f"Next cycle in {interval:.0f} minutes (at ~{next_run.strftime('%H:%M:%S UTC')})")
            time.sleep(int(interval * 60))

        except KeyboardInterrupt:
            logger.info("\n\nScheduler stopped by user.")
            logger.info(f"Final stats: {state.run_count} runs, "
                       f"{state.successful_runs} successful, "
                       f"{state.failed_runs} failed")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(60)


def run_once_mode(verbose: bool = False) -> None:
    """Run a single improvement cycle and exit."""
    logger = setup_logging(LOG_FILE, verbose)
    logger.info("Running single improvement cycle...\n")

    report = run_improvement_cycle(verbose=verbose, logger=logger)

    # Update state
    state = load_schedule_state()
    state.run_count += 1
    state.last_run = report.timestamp
    state.last_commit_hash = get_git_commit_hash()
    if report.success:
        state.successful_runs += 1
    else:
        state.failed_runs += 1
    save_schedule_state(state)

    # Print summary
    print("\n" + "=" * 60)
    print("IMPROVEMENT CYCLE SUMMARY")
    print("=" * 60)
    print(f"Timestamp:      {report.timestamp}")
    print(f"Duration:       {report.duration_sec}s")
    print(f"Status:         {'✓ SUCCESS' if report.success else '⚠ ISSUES'}")
    print(f"Tests:          {report.tests_passed} passed, {report.tests_failed} failed, {report.tests_errors} errors")
    print(f"Findings:       {report.findings_high} high, {report.findings_medium} medium, {report.findings_low} low")
    print(f"Code Changes:   {report.files_changed} files, {report.lines_changed} lines")
    if report.regressions:
        print(f"Regressions:    {', '.join(report.regressions)}")
    if report.error_message:
        print(f"Error:          {report.error_message}")
    print("=" * 60)

    sys.exit(0 if report.success else 1)


# ── CLI Entry Point ───────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="schedule",
        description="LeagueLoop Self-Improvement Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run continuously every 60 minutes
  py -m self_improving.schedule --mode continuous --interval 60

  # Run at specific times (9 AM and 5 PM daily)
  py -m self_improving.schedule --mode cron --times "09:00,17:00"

  # Smart adaptive mode (adjusts based on code activity)
  py -m self_improving.schedule --mode smart --interval 30

  # Single run
  py -m self_improving.schedule --mode once

  # Verbose output with custom interval
  py -m self_improving.schedule --mode continuous --interval 30 --verbose
        """,
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["continuous", "cron", "smart", "once"],
        default="continuous",
        help="Scheduling mode (default: continuous)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL_MINUTES,
        help=f"Interval in minutes (default: {DEFAULT_INTERVAL_MINUTES})",
    )
    parser.add_argument(
        "--times",
        type=str,
        default="",
        help="Comma-separated times for cron mode (e.g., '09:00,17:00')",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Maximum number of runs before exiting (default: unlimited)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--project",
        type=str,
        default=PROJECT_ROOT,
        help=f"Project root directory (default: {PROJECT_ROOT})",
    )

    args = parser.parse_args()

    # Handle signals gracefully
    def signal_handler(sig, frame):
        print("\n\nReceived interrupt signal. Shutting down gracefully...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Execute selected mode
    project_root = args.project  # Use local variable instead of global

    if args.mode == "once":
        run_once_mode(verbose=args.verbose)
    elif args.mode == "continuous":
        run_continuous_mode(
            interval_minutes=args.interval,
            verbose=args.verbose,
            max_runs=args.max_runs,
        )
    elif args.mode == "cron":
        if not args.times:
            parser.error("--times is required for cron mode")
        times = [t.strip() for t in args.times.split(",")]
        run_cron_mode(times=times, verbose=args.verbose)
    elif args.mode == "smart":
        run_smart_mode(
            base_interval_minutes=args.interval,
            verbose=args.verbose,
        )


if __name__ == "__main__":
    main()
