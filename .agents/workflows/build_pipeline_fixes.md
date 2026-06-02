---
description: Build pipeline fixes and instructions for the LeagueLoop Installer
---

# LeagueLoop Build Pipeline Reference

This document contains the historical context of all build issues encountered and solved, plus the canonical build commands.

## Known Issues & Solutions

### 1. The `run.py` Entry Point Mismatch
- **Problem:** `run.py` imported `App` instead of `LeagueLoopApp`.
- **Fix:** Updated to import `LeagueLoopApp`.

### 2. ONEFILE vs ONEDIR Packaging
- **Problem:** `LeagueLoop.spec` used ONEFILE, but `installer.iss` expected ONEDIR layout.
- **Fix:** Switched to COLLECT pipeline producing `dist/LeagueLoop/` directory.

### 3. Missing ISCC.exe
- **Problem:** Inno Setup not installed on build machine.
- **Fix:** Installed to `C:\InnoSetup\`. Agent should probe this path.

### 4. Logger PermissionError in Program Files
- **Problem:** Logger wrote to CWD which is read-only under `C:\Program Files\`.
- **Fix:** Redirected to `%APPDATA%\LeagueLoop\` with fallback.

### 5. Binary Patch Errors in Git
- **Problem:** `git stash pop` fails on `.exe`/`.pyz` files with "cannot apply binary patch without full index line".
- **Fix:** Never stage `build/` or `dist/` contents. If stash is corrupt: `git restore --staged build/ && git restore build/ && git stash drop`.

### 6. PYTHONPATH Import Failures
- **Problem:** Running `python core/main.py` directly breaks sibling imports.
- **Fix:** Always use `$env:PYTHONPATH="<project>\src"; python -m core.main`.

---

## Canonical Build Commands

```powershell
# Full clean build
cd c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist\LeagueLoop) { Remove-Item -Recurse -Force dist\LeagueLoop }
.venv\Scripts\pyinstaller --clean LeagueLoop.spec 2>&1

# Compile installer
& "C:\InnoSetup\ISCC.exe" "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\installer.iss" 2>&1
```

## Key Paths
| Asset | Path |
|-------|------|
| Spec file | `c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\LeagueLoop.spec` |
| ISS script | `c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\installer.iss` |
| PyInstaller output | `dist\LeagueLoop\` |
| Installer output | `dist\LeagueLoop_Installer.exe` |
| Inno Setup compiler | `C:\InnoSetup\ISCC.exe` |
| Python venv | `.venv\Scripts\python.exe` |
