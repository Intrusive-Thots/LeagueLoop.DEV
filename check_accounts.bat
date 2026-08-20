@echo off
title LeagueLoop - Account Preflight
cd /d "%~dp0"
set PYTHONPATH=%CD%\src
set ACCLOG=%CD%\accounts_check.log

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv
    pause
    exit /b 1
)

echo.
echo  Running account switching preflight ^(read-only^)...
echo.

".venv\Scripts\python.exe" -u tools\check_accounts.py %* > "%ACCLOG%" 2>&1
type "%ACCLOG%"

echo.
echo  Saved to: %ACCLOG%
echo.
pause
