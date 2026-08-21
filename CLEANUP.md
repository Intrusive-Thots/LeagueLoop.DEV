# Housekeeping — files to delete

I cannot delete or move files on your machine from here; the bridge only
reads and writes. So this is the list, with a command you can paste. Every
entry below was checked for references first — nothing here is imported,
called, or collected by anything.

Run from `C:\Users\Malcolm\LeagueLoop.DEV`:

```
git rm -r --cached --ignore-unmatch ^
  hotkey_test.log startup_diagnostic.log qt_startup.log accounts_check.log

git rm --ignore-unmatch ^
  fix_import.py test_hotkey.py test_hotkeys_config.py test_launcher.py test_tokens.py ^
  src/core/state_manager.py ^
  IMPLEMENTATION_PLAN.md IMPROVEMENTS_SUMMARY.md ^
  PERFORMANCE_OPTIMIZATION_PLAN.md PERFORMANCE_OPTIMIZATION_REPORT.md ^
  TASK_QUEUE.md TODO.md task.md

del /q lcu_capture.json 2>nul
rd /s /q src\ui\qt\__pycache__ src\ui\qt\services\__pycache__
```

## Why each one

### Scratch scripts named like tests

`fix_import.py` is a one-shot regex patcher for `friend_list.py` — it ran
once, months ago, and rewrites a file on import. `test_hotkey.py`,
`test_hotkeys_config.py` and `test_launcher.py` are throwaway probes that
execute at import time (`test_launcher.py` reads the registry). None are
tests. `pytest.ini` sets `testpaths = tests`, so they are not collected today
— but they are named `test_*` at the repo root, so the first person to run
`pytest .` gets registry reads and keyboard hooks instead of a test run.

`test_tokens.py` **was** a real test, but it imported
`src.ui.theme.token_loader`, which cannot resolve under `pythonpath = src`,
and lived where pytest never looked. It could not have passed if it had been
collected. I have rewritten it as `tests/test_design_tokens.py`, which passes
— delete the original.

### Dead module

`src/core/state_manager.py` — nothing imports it. `StateManager` lives in
`src/core/state.py`; this is an older copy that was never removed, and having
two files with that name is an actively misleading way to leave a repo.

### Logs

`hotkey_test.log`, `startup_diagnostic.log`, `qt_startup.log`,
`accounts_check.log`. `.gitignore` already covers `*.log`, so these are
untracked clutter rather than committed clutter — the `git rm --cached` line
is only there in case any slipped in before the rule existed.

### Stale bytecode with no source

`src/ui/qt/services/__pycache__/tray_service.cpython-312.pyc` and
`src/ui/qt/__pycache__/theme.cpython-312.pyc` are compiled from source files
that no longer exist (`theme` is a package now, not a module). Harmless —
Python will not import from `__pycache__` without the source — but they are
evidence of deleted files and make the tree read as if those modules exist.

### Overlapping planning documents

`IMPLEMENTATION_PLAN.md`, `IMPROVEMENTS_SUMMARY.md`,
`PERFORMANCE_OPTIMIZATION_PLAN.md`, `PERFORMANCE_OPTIMIZATION_REPORT.md`,
`TASK_QUEUE.md`, `TODO.md`, `task.md` — seven documents describing intended
work, none of them current. `LeagueLoop_Handover_TODO.md` in the Claude
project supersedes all of them. Keep `README.md`, `CHANGELOG.md`,
`CONTEXT.md`, `AGENTS.md`, `ROADMAP.md` and the installer guide.

## Cleaned up in code (already committed)

- `src/ui/qt/widgets/__init__.py` re-exported exactly one name,
  `TransparentOverlayWidget` — an orphaned widget nothing uses. Importing the
  widgets package pulled in dead code and advertised the one thing the app
  never touches. The file is now documentation only.
- `tests/test_design_tokens.py` replaces the uncollectable root test, and adds
  a test documenting a real trap in `DesignTokens.get()`: it inspects the last
  *positional* argument and promotes it to the default if it looks like one (a
  colour, `"bold"`, `"center"`, any number). `get("spacing", "md")` reads a
  nested key; `get("colors", "bold")` silently becomes a lookup with a
  fallback. Callers cannot tell which they wrote. Worth fixing properly —
  make `default` keyword-only and delete the heuristic.

## Left alone deliberately

- `src/ui/qt/widgets/transparent_overlay.py` — orphaned, but `orb_widget.py`
  now exists and may be intended to supersede it. Deleting it is a product
  decision, not housekeeping. It is on the handover list.
- `src/ui/qt/widgets/priority_tab.py` — a 10-line shim re-exporting from
  `champion_list_tab`. Harmless, and it keeps older imports working.
- `core.state.State` — the legacy mutable global. Still genuinely used
  (`automation.py` for the friend list, `main.py` for assets), so it is a
  migration, not a deletion. It is a second source of truth alongside
  `ApplicationState` and belongs on the handover list, which it is on.
- `scratch/`, `cache/`, `build/`, `dist/`, `memory/` — already gitignored.
