@echo off
title LeagueLoop — Dev Mode
cd /d "%~dp0"
set PYTHONPATH=%CD%\src

echo.
echo  ============================================
echo   LeagueLoop — Development Mode
echo  ============================================
echo.

".venv\Scripts\python.exe" run.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  !! CRASHED — see output above for errors
    echo.
    pause
)
