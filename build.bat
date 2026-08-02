@echo off
setlocal EnableDelayedExpansion
title LeagueLoop Build Pipeline
color 0A

echo.
echo  ============================================
echo   LeagueLoop Build Pipeline
echo  ============================================
echo.

:: ── Step 1: Read version from source ────────────
for /f "tokens=2 delims==" %%a in ('findstr /C:"__version__" src\core\version.py') do (
    set "RAW=%%a"
)
:: Trim quotes and spaces
set "VER=%RAW: =%"
set "VER=%VER:"=%"
echo  Version: %VER%
echo.

:: ── Step 2: Clean previous builds ───────────────
echo  [1/4] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist\LeagueLoop rmdir /s /q dist\LeagueLoop
if exist dist\LeagueLoop.exe del /f /q dist\LeagueLoop.exe
if exist dist\LeagueLoop_Installer.exe del /f /q dist\LeagueLoop_Installer.exe
:: Purge ALL __pycache__ dirs so PyInstaller recompiles from fresh .py sources
for /d /r src %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
echo        Done.
echo.

:: ── Step 3: PyInstaller (ONEDIR) ────────────────
echo  [2/4] Building LeagueLoop executable...
echo        This will take a moment, gathering all dependencies...
echo.
.venv\Scripts\pyinstaller.exe --clean -y LeagueLoop.spec
echo.

if not exist dist\LeagueLoop\LeagueLoop.exe (
    color 0C
    echo  !!  BUILD FAILED — check output above for errors
    echo.
    pause
    exit /b 1
)
echo  [2/4] PyInstaller build complete!
echo        Output: dist\LeagueLoop\
echo.

:: ── Step 4: Inno Setup Installer ────────────────
echo  [3/4] Creating installer with Inno Setup (Version: %VER%)...
:: Convert 1-04-264-0219 format to 1.4.264.219 for Windows VersionInfo format
set "VER_FORMATTED=%VER:-=.%"
"C:\InnoSetup\ISCC.exe" /DAppVersion="%VER%" /DVersionInfoVersion="%VER_FORMATTED%" installer.iss
echo.

if not exist dist\LeagueLoop_Installer.exe (
    color 0E
    echo  !!  Installer creation failed — check Inno Setup output
    echo.
    pause
    exit /b 1
)
echo  [3/4] Installer created!
echo        Output: dist\LeagueLoop_Installer.exe
echo.

:: ── Step 5: Copy to Installer repo ──────────────
echo  [4/4] Copying installer to LeagueLoop-Installer repo...
set "INSTALLER_REPO=%USERPROFILE%\Desktop\LeagueLoop-Installer"
if exist "%INSTALLER_REPO%" (
    copy /Y "dist\LeagueLoop_Installer.exe" "%INSTALLER_REPO%\LeagueLoop_Installer.exe" >nul
    echo        Copied to: %INSTALLER_REPO%\
) else (
    echo        WARNING: Installer repo not found at %INSTALLER_REPO%
    echo        Skipping copy. The installer is at dist\LeagueLoop_Installer.exe
)
echo.

:: ── Summary ─────────────────────────────────────
echo  ============================================
echo   BUILD COMPLETE
echo   Version:   %VER%
echo   Executable: dist\LeagueLoop\LeagueLoop.exe
echo   Installer:  dist\LeagueLoop_Installer.exe
echo  ============================================
echo.
pause
