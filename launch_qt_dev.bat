@echo off
title LeagueLoop — Qt (PySide6) DEV Tester
cd /d "%~dp0"
set PYTHONPATH=%CD%\src

echo.
echo  ============================================
echo   LeagueLoop — Qt Shell (PySide6)
echo  ============================================
echo.
echo   This is the NEW UI, still in migration.
echo   The production UI is still launch_dev.bat.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv!
    echo Please run install.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -c "import PySide6" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PySide6 is not installed in .venv.
    echo.
    echo   Install the migration dependencies with:
    echo     .venv\Scripts\python.exe -m pip install -r requirements-qt.txt
    echo.
    pause
    exit /b 1
)

REM Pass through any arguments, e.g. --no-services
".venv\Scripts\python.exe" run_qt.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  !! LeagueLoop Qt shell exited with code %ERRORLEVEL%
    echo  See log output above for details.
    echo.
    pause
)
