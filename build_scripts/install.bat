@echo off
setlocal EnableDelayedExpansion
title LeagueLoop Setup and Installer
color 0A

echo.
echo  ================================================
echo             LeagueLoop Automated Setup
echo  ================================================
echo.

:: ── Step 1: Check Python Installation ───────────
echo  [1/4] Checking Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo  !! ERROR: Python is not installed or not in PATH.
    echo  Please install Python 3.10 or newer from python.org and try again.
    echo.
    pause
    exit /b 1
)
echo        Python is installed.
echo.

:: ── Step 2: Install Prerequisites ───────────────
echo  [2/4] Installing prerequisites and libraries...
echo        This may take a moment.
python -m pip install --upgrade pip >nul
if exist requirements.txt (
    python -m pip install -r requirements.txt
) else (
    color 0E
    echo  !! WARNING: requirements.txt not found!
    echo     Dependencies may not be installed correctly.
)
python -m pip install pyinstaller
echo.

:: ── Step 3: Build LeagueLoop Executable ─────────
echo  [3/4] Compiling LeagueLoop...
echo        Building standalone executable using PyInstaller.
echo.
pyinstaller --clean LeagueLoop.spec
echo.

if not exist dist\LeagueLoop\LeagueLoop.exe (
    color 0C
    echo  !! ERROR: Build failed. Check the output above.
    echo.
    pause
    exit /b 1
)
echo  [3/4] Build complete!
echo.

:: ── Step 4: Launch LeagueLoop ───────────────────
echo  [4/4] Launching LeagueLoop...
echo  ================================================
echo.
start "" "dist\LeagueLoop\LeagueLoop.exe"

echo  LeagueLoop successfully installed and launched!
echo  You can close this window now.
echo.
pause
