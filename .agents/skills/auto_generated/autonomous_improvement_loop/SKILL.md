---
name: autonomous_improvement_loop
description: |
  Auto-generated skill for running the LeagueLoop.DEV Autonomous Improvement Loop.
  Provides automated orchestration across diagnostics, fast AST regression testing,
  codebase metric indexing, and capability memory updates.
license: Apache-2.0
metadata:
  version: v1.0.0
  target_project: C:\Users\Malcolm\LeagueLoop.DEV\
---

# Autonomous Improvement Loop Skill

Use this skill to autonomously execute the LeagueLoop.DEV improvement cycle.

## Core Capabilities

1. **Diagnostics Inspection**:
   Evaluates `%LOCALAPPDATA%\LeagueLoop\logs\error.log`, `crash.log`, and `debug_screenshots\`.
   ```powershell
   .venv\Scripts\python.exe tools/leagueloop_diagnostics.py --summary
   ```

2. **AST-Driven Targeted Testing**:
   Executes pytest targets mapped via AST imports in <2 seconds.
   ```powershell
   .venv\Scripts\python.exe tools/fast_test_runner.py
   ```

3. **Autonomous Improvement Orchestrator**:
   Profiles codebase metrics (file count, python lines), verifies tests, updates `loop_state.json`, and records to `episodic.json` and `optimizations.json`.
   ```powershell
   .venv\Scripts\python.exe tools/autonomous_improvement_runner.py --all-tests
   ```
