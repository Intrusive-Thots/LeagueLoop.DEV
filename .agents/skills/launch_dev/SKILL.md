---
name: Launch Dev Server
description: Launch the LeagueLoop application in development mode with proper PYTHONPATH
---

# Launch Dev Server

## Steps

1. Set PYTHONPATH and run via module mode:
```powershell
$env:PYTHONPATH = "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\src"
& "c:\Users\Administrator\antigravity-worspaces-1\antigravity-worspaces\.venv\Scripts\python.exe" -m core.main
```

Or use the batch launcher:
```powershell
& "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\launch_dev.bat"
```

## Critical Rules
- **NEVER** run `python core/main.py` directly — it breaks sibling package imports (`services`, `ui`, `utils`).
- **ALWAYS** use `-m core.main` with PYTHONPATH set to the project root.
- The venv is at `.venv\Scripts\python.exe`.
- `launch_dev.bat` handles all of this automatically and pauses on crash for debugging.
