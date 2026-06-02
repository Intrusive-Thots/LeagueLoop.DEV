---
name: Build Executable
description: Build the LeagueLoop PyInstaller executable in ONEDIR mode
---

# Build Executable

## Steps

1. Activate the project venv:
```powershell
& "c:\Users\Administrator\antigravity-worspaces-1\antigravity-worspaces\.venv\Scripts\Activate.ps1"
```

2. Run PyInstaller with the spec file:
```powershell
pyinstaller LeagueLoop.spec --clean --noconfirm
```

3. Verify the output exists:
```powershell
Test-Path "dist\LeagueLoop\LeagueLoop.exe"
```

4. Test-launch the built executable:
```powershell
& "dist\LeagueLoop\LeagueLoop.exe"
```

## Notes
- Always use ONEDIR mode (not ONEFILE) to match the Inno Setup installer expectations.
- The spec file is at the project root: `LeagueLoop.spec`.
- Output lands in `dist/LeagueLoop/`.
- If you get import errors, ensure all dependencies are in `requirements.txt` and installed into the venv.
