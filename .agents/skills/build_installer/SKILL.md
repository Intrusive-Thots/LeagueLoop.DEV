---
name: Build Installer
description: Compile the Inno Setup installer for LeagueLoop distribution
---

# Build Installer

## Prerequisites
- A successful PyInstaller build (see `build_executable` skill).
- Inno Setup installed at `C:\InnoSetup\ISCC.exe`.

## Steps

1. Ensure the `dist/LeagueLoop/` directory is up to date from a fresh PyInstaller build.

2. Compile the installer:
```powershell
& "C:\InnoSetup\ISCC.exe" "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\installer.iss" 2>&1
```

3. Verify the output:
```powershell
Test-Path "dist\LeagueLoop_Installer.exe"
[math]::Round((Get-Item "dist\LeagueLoop_Installer.exe").Length/1MB, 2)
```

## Publishing to Installer Repo
After building, copy to the public installer repo:
```powershell
Copy-Item "dist\LeagueLoop_Installer.exe" "c:\Users\Administrator\Desktop\LeagueLoop-Installer\LeagueLoop_Installer.exe" -Force
cd c:\Users\Administrator\Desktop\LeagueLoop-Installer
git add -A
git commit -m "release: update installer"
git push origin master
```

## Notes
- The `installer.iss` script expects PyInstaller ONEDIR output in `dist\LeagueLoop\`.
- Always rebuild the executable before recompiling the installer.
- The installer repo (`LeagueLoop-Installer`) contains ONLY the `.exe`, icon, screenshots, and README — no source code.
- The installer uses the custom `assets\app.ico` for branding.
