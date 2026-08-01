# LeagueLoop Self-Improvement Scheduler

A production-ready scheduler for running automated code improvement cycles on the LeagueLoop codebase.

## Features

### Multiple Scheduling Modes

1. **Continuous Mode** - Run improvement cycles at fixed intervals
   ```bash
   py -m self_improving.schedule --mode continuous --interval 60
   ```

2. **Cron Mode** - Run at specific times of day
   ```bash
   py -m self_improving.schedule --mode cron --times "09:00,17:00"
   ```

3. **Smart Adaptive Mode** - Automatically adjusts interval based on code activity
   ```bash
   py -m self_improving.schedule --mode smart --interval 30
   ```

4. **Once Mode** - Single run for testing
   ```bash
   py -m self_improving.schedule --mode once
   ```

### What Each Cycle Does

Every improvement cycle performs:

1. **Repository Scan** - Indexes all files, counts lines, finds TODOs
2. **Test Suite Execution** - Runs pytest and captures results
3. **Regression Detection** - Compares against baseline to catch issues
4. **Static Analysis** - Identifies:
   - Complex files that need refactoring
   - Missing docstrings
   - Modules without test coverage
   - TODO/FIXME/HACK comments
5. **Memory Persistence** - Logs findings to `.agents/memory/`
6. **Code Change Detection** - Tracks git diffs since last run

### Advanced Features

- **Resource Monitoring** - Skips cycles if CPU/memory usage is too high
- **Error Recovery** - Exponential backoff on repeated failures
- **Graceful Shutdown** - Handles SIGINT/SIGTERM properly
- **Detailed Logging** - Console + file logging with timestamps
- **State Persistence** - Remembers run history across restarts
- **Git Integration** - Tracks commit hashes and code changes

## Usage Examples

### Basic Setup (Run Every Hour)
```bash
# Start the scheduler in continuous mode
py -m self_improving.schedule --mode continuous --interval 60
```

### Development Testing (Quick Feedback)
```bash
# Run every 15 minutes with verbose output
py -m self_improving.schedule --mode continuous --interval 15 --verbose
```

### Daily Scheduled Runs
```bash
# Run at 9 AM and 5 PM on weekdays
py -m self_improving.schedule --mode cron --times "09:00,17:00"
```

### Smart Adaptive (Recommended for Active Development)
```bash
# Automatically adjusts frequency based on code changes
py -m self_improving.schedule --mode smart --interval 30
```

### Limited Test Run
```bash
# Run exactly 5 cycles then exit
py -m self_improving.schedule --mode continuous --interval 10 --max-runs 5
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--mode` | Scheduling mode: `continuous`, `cron`, `smart`, `once` | `continuous` |
| `--interval` | Minutes between cycles | `60` |
| `--times` | Comma-separated times for cron mode (e.g., `"09:00,17:00"`) | Required for cron |
| `--max-runs` | Maximum runs before exiting | Unlimited |
| `--verbose`, `-v` | Enable detailed output | Off |
| `--project` | Project root directory | Current project |

## Output Files

The scheduler creates these files in `.agents/memory/`:

- `schedule_state.json` - Scheduler state (run count, last run time, etc.)
- `schedule.log` - Detailed log of all cycles
- `episodic.json` - Episode memory entries
- `loop_state.json` - Test baselines and run metadata

## Interpreting Results

After each cycle, you'll see a summary like:

```
============================================================
IMPROVEMENT CYCLE SUMMARY
============================================================
Timestamp:      2026-07-31T20:57:53.010884+00:00
Duration:       0.225s
Status:         ✓ SUCCESS
Tests:          195 passed, 0 failed, 0 errors
Findings:       0 high, 75 medium, 50 low
Code Changes:   3 files, +120 lines
============================================================
```

### Status Indicators

- **✓ SUCCESS** - All tests passed, no regressions
- **⚠ ISSUES** - Findings detected or regressions found

### Finding Severities

- **High** - Critical issues (files >300 lines needing refactoring)
- **Medium** - Important improvements (missing tests, TODOs)
- **Low** - Nice-to-have fixes (missing docstrings)

## Integration with CI/CD

Add to your GitHub Actions workflow:

```yaml
- name: Run Self-Improvement Cycle
  run: |
    python -m self_improving.schedule --mode once --verbose
```

## Windows Task Scheduler

To run automatically on Windows:

1. Open Task Scheduler
2. Create Basic Task → "LeagueLoop Self-Improvement"
3. Trigger: Daily at 9:00 AM
4. Action: Start a program
   - Program: `python.exe`
   - Arguments: `-m self_improving.schedule --mode once`
   - Start in: `C:\path\to\LeagueLoop.DEV`

## Troubleshooting

### Tests Not Running
Ensure pytest is installed and working:
```bash
pip install pytest
python -m pytest tests/ --verbose
```

### High Resource Usage Warnings
Increase limits in `schedule.py`:
```python
MAX_CPU_PERCENT = 90  # Default: 80
MAX_MEMORY_MB = 4096  # Default: 2048
```

### Permission Errors
Run as administrator or check file permissions in `.agents/memory/`.

## Architecture

```
self_improving/
├── __init__.py          # Module documentation
├── __main__.py          # Original loop entry point
├── schedule.py          # NEW: Production scheduler
├── repo_index.py        # Repository scanning
├── test_runner.py       # Pytest execution
├── analyzers.py         # Static analysis passes
└── memory.py            # Persistent storage
```

## Best Practices

1. **Start with `--mode once`** to verify everything works
2. **Use `--verbose`** during initial setup
3. **Monitor logs** in `.agents/memory/schedule.log`
4. **Adjust intervals** based on your development pace
5. **Review findings** regularly and address high-severity items

## License

MIT License - Part of LeagueLoop.DEV
