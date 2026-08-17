# LeagueLoop Installer Build Guide

## Overview
This repository now includes a cross-platform installer build system using NSIS (Nullsoft Scriptable Install System) that can be built on Windows through GitHub Actions.

## Built Installer
A Windows installer has been successfully built:
- **File**: `dist/LeagueLoop_Installer.exe`
- **Size**: ~65 MB
- **Version**: 1-08-137-2319

## How to Build the Installer

### Option 1: Automated via GitHub Actions (Recommended)

The GitHub Actions workflow will automatically build the installer when:
1. You push a tag starting with `v*` (e.g., `v1.0.0`)
2. You manually trigger the workflow from the Actions tab

**To create a release:**
```bash
git tag v1.0.0
git push origin v1.0.0
```

This will:
- Build the application with PyInstaller on Windows
- Create the NSIS installer
- Upload the installer as a GitHub Release artifact

### Option 2: Manual Build on Windows

If you want to build locally on Windows:

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt pyinstaller
   ```

2. **Install NSIS:**
   - Download from: https://nsis.sourceforge.io/Download
   - Or use Chocolatey: `choco install nsis -y`

3. **Build PyInstaller executable:**
   ```bash
   pyinstaller --clean -y LeagueLoop.spec
   ```

4. **Build Installer:**
   ```bash
   makensis -V2 installer.nsi
   ```

5. **Output:** `dist\LeagueLoop_Installer.exe`

## Installer Features

The NSIS installer includes:
- ✅ Modern UI with welcome and finish pages
- ✅ License agreement page
- ✅ Custom installation directory
- ✅ Start Menu shortcut
- ✅ Desktop shortcut (optional)
- ✅ Automatic cleanup of stale log files from previous installs
- ✅ Proper Windows uninstaller with registry entries
- ✅ Auto-launch option after installation
- ✅ Admin privileges for Program Files installation

## Uploading to Installer Repository

Since there's no direct git remote configured, you have several options:

### Option A: GitHub Releases (Recommended)
Use the automated workflow above - it creates releases automatically.

### Option B: Manual Upload
1. Download `dist/LeagueLoop_Installer.exe` from the Actions artifact
2. Go to your GitHub repository → Releases
3. Create a new release or edit existing one
4. Upload the installer file

### Option C: Clone Installer Repo
If you have a separate `LeagueLoop-Installer` repository:
```bash
git clone <installer-repo-url> ../LeagueLoop-Installer
copy dist\LeagueLoop_Installer.exe ..\LeagueLoop-Installer\
cd ../LeagueLoop-Installer
git add LeagueLoop_Installer.exe
git commit -m "Update to version 1-08-137-2319"
git push
```

## Files Added

- `installer.nsi` - NSIS script for building the Windows installer
- `.github/workflows/build-installer.yml` - GitHub Actions workflow for automated builds

## Migration from Inno Setup

The original `build.bat` and `installer.iss` files are still present for backward compatibility. The new NSIS-based approach offers:
- Cross-platform build capability (via GitHub Actions on Windows)
- Simpler dependency management (NSIS is available via choco)
- Similar feature set to Inno Setup
- Better integration with GitHub Actions

## Troubleshooting

**Build fails on GitHub Actions:**
- Check the Actions logs for specific errors
- Ensure all paths in `installer.nsi` match the PyInstaller output structure

**Installer too large:**
- The 65MB size includes all Python dependencies bundled by PyInstaller
- Consider using UPX compression in the PyInstaller spec file

**NSIS warnings:**
- The warning about MUI_PAGE_* order is harmless and doesn't affect functionality
