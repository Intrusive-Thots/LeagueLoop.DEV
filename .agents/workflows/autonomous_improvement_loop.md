---
description: Autonomous Improvement Loop workflow for LeagueLoop.DEV
---
// turbo-all

# Autonomous Improvement Loop Workflow

Executes diagnostics, AST-directed regression test checks, metric extraction, memory synchronization, and MemPalace journaling.

## Steps

1. Inspect diagnostic status across error.log, crash.log, and debug_screenshots:
```powershell
.venv\Scripts\python.exe tools/leagueloop_diagnostics.py --summary
```

2. Run code entropy audit summary across codebase:
```powershell
.venv\Scripts\python.exe tools/code_entropy_analyzer.py --summary
```

3. Run targeted test verification using AST dependency graph mapping:
```powershell
.venv\Scripts\python.exe tools/fast_test_runner.py
```

4. Execute full autonomous improvement loop orchestration (profiles metrics and updates loop_state.json):
```powershell
.venv\Scripts\python.exe tools/autonomous_improvement_runner.py --all-tests
```

5. Verify git changes:
```powershell
git status -s
```
