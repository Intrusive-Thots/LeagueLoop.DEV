# LeagueLoop Workspace Rules & Specialist Instructions

## 1. Environment & Target Directory
- **Dev Directory**: `C:\Users\Malcolm\LeagueLoop.DEV\`
- **NEVER** edit files in secondary clones, desktop copies, or fallback folders (`didactic-spoon`, desktop folders).

## 2. Error Logs & Screenshot Inspection (Always Check First)
When investigating bugs, exceptions, or user issues:
1. **Error Logs**: Inspect `%LOCALAPPDATA%\LeagueLoop\logs\error.log` and `crash.log`. Check `debug.log` and `session.jsonl` for full trace.
2. **Screenshots**: Inspect `%LOCALAPPDATA%\LeagueLoop\debug_screenshots\` for the most recent `.png` files (UI actions, game phase changes, crash triggers). Fallback: `C:\Users\Malcolm\Desktop\Captures`.
3. **Always address root causes** found in these logs and captures before declaring a fix complete.

## 3. Version Bump Requirement on Every PR
- **Rule**: Every time you prepare to push commits for a PR or open a PR to GitHub (`origin` or `public`):
  1. Run `python tools/bump_version.py` from `C:\Users\Malcolm\LeagueLoop.DEV\`.
  2. Verify `src/core/version.py` is updated.
  3. Update `installer.iss` (`AppVersion` & `VersionInfoVersion`) to match if applicable.
  4. Stage and commit the bumped version with the PR.

## 4. Installer Repo Creation (Strictly on User Request)
- **Controlled Compilation Invariant**: NEVER run `build.bat`, PyInstaller, or Inno Setup automatically.
- **When Instructed by User**:
  1. Verify version is updated in `src/core/version.py` and `installer.iss`.
  2. Clean build:
     ```powershell
     cd C:\Users\Malcolm\LeagueLoop.DEV
     if (Test-Path build) { Remove-Item -Recurse -Force build }
     if (Test-Path dist\LeagueLoop) { Remove-Item -Recurse -Force dist\LeagueLoop }
     .venv\Scripts\pyinstaller --clean -y LeagueLoop.spec
     & "C:\InnoSetup\ISCC.exe" "C:\Users\Malcolm\LeagueLoop.DEV\installer.iss"
     ```
  3. Copy output `dist\LeagueLoop_Installer.exe` to installer repo:
     `Copy-Item "C:\Users\Malcolm\LeagueLoop.DEV\dist\LeagueLoop_Installer.exe" -Destination "C:\Users\Malcolm\Desktop\LeagueLoop-Installer\LeagueLoop_Installer.exe" -Force`
  4. In `C:\Users\Malcolm\Desktop\LeagueLoop-Installer\`:
     - Update version in `README.md`.
     - Git stage, commit (`git commit -m "Update LeagueLoop Installer to v<version>"`), and push to `origin` (`git@github.com:Intrusive-Thots/LeagueLoop-Installer.git`).
