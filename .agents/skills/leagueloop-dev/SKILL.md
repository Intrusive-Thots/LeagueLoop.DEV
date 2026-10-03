---
name: leagueloop-dev
description: |
  Specialized engineering and maintenance protocol for LeagueLoop.DEV (League of Legends client automation).
  Provides rules and workflows for reading error logs and debug screenshots, enforcing version bumps on every PR,
  and building/deploying updated installers to the LeagueLoop-Installer repository when instructed.
license: Apache-2.0
metadata:
  version: v1.0.0
  target_project: C:\Users\Malcolm\LeagueLoop.DEV\
---

# LeagueLoop.DEV Specialist Skill

Use this skill whenever working on, debugging, testing, or deploying LeagueLoop.

## 1. Workspace Boundaries
- **Active Workspace**: `C:\Users\Malcolm\LeagueLoop.DEV\`
- **Virtual Environment**: `C:\Users\Malcolm\LeagueLoop.DEV\.venv\Scripts\python.exe`
- **Rule**: NEVER edit secondary clones, desktop copies, or fallback directories.

## 2. Error Logs & Screenshot Protocol (Mandatory First Step)
Before fixing any issue or concluding a task:
1. **Error Logs**:
   - Inspect `%LOCALAPPDATA%\LeagueLoop\logs\error.log` (WARNING/ERROR/CRITICAL with tracebacks).
   - Check `%LOCALAPPDATA%\LeagueLoop\logs\crash.log` for unhandled fatal process exits.
   - Inspect `%LOCALAPPDATA%\LeagueLoop\logs\debug.log` and `session.jsonl` for execution context.
2. **Debug Screenshots**:
   - Inspect `%LOCALAPPDATA%\LeagueLoop\debug_screenshots\` for the most recent `.png` files.
   - Screenshots capture UI button clicks, tab transitions, champion hover/lock attempts, and game phase changes.
   - Fallback screenshots: `C:\Users\Malcolm\Desktop\Captures\`.
3. **Action**:
   - Trace the exact line and component responsible for the logged failure or unexpected screenshot state.
   - Always verify that the fix clears or prevents reproduction of the error.

## 3. Version Number Bump Protocol (On Every PR)
Every time a pull request is prepared or changes are pushed to an online repository branch:
1. Run version bump tool from `C:\Users\Malcolm\LeagueLoop.DEV\`:
   ```powershell
   python tools/bump_version.py
   ```
2. Verify `src/core/version.py` contains the updated version string (`{major}-{month}-{day_of_year}-{HHMM}`).
3. Check and align `installer.iss`:
   - Update `#define AppVersion` and `#define VersionInfoVersion` if necessary.
4. Stage and commit the bumped version file with the PR branch commits before pushing:
   ```powershell
   git add src/core/version.py installer.iss
   git commit -m "Bump version for PR"
   git push origin <branch-name>
   ```

## 4. Installer Repo Build & Deployment (Strictly On User Instruction)
Never build or compile installers automatically. When explicitly instructed by the user:
1. **Verify Version**: Run `python tools/bump_version.py --check` or bump it.
2. **Clean & Compile LeagueLoop**:
   ```powershell
   cd C:\Users\Malcolm\LeagueLoop.DEV
   if (Test-Path build) { Remove-Item -Recurse -Force build }
   if (Test-Path dist\LeagueLoop) { Remove-Item -Recurse -Force dist\LeagueLoop }
   if (Test-Path dist\LeagueLoop_Installer.exe) { Remove-Item -Force dist\LeagueLoop_Installer.exe }
   .venv\Scripts\pyinstaller --clean -y LeagueLoop.spec
   & "C:\InnoSetup\ISCC.exe" "C:\Users\Malcolm\LeagueLoop.DEV\installer.iss"
   ```
3. **Verify Built Installer**:
   Confirm `dist\LeagueLoop_Installer.exe` was successfully created.
4. **Deploy to Installer Repo**:
   - Installer Repo Path: `C:\Users\Malcolm\Desktop\LeagueLoop-Installer\`
   - Copy the executable:
     ```powershell
     Copy-Item "C:\Users\Malcolm\LeagueLoop.DEV\dist\LeagueLoop_Installer.exe" -Destination "C:\Users\Malcolm\Desktop\LeagueLoop-Installer\LeagueLoop_Installer.exe" -Force
     ```
   - Update `C:\Users\Malcolm\Desktop\LeagueLoop-Installer\README.md` with new version details.
   - Commit and push to remote:
     ```powershell
     cd C:\Users\Malcolm\Desktop\LeagueLoop-Installer
     git add LeagueLoop_Installer.exe README.md
     git commit -m "Update LeagueLoop Installer to latest release"
     git push origin master
     ```
