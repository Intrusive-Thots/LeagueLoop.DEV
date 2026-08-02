@echo off
title Queqq — DEV Tester
cd /d "%~dp0"
set PYTHONPATH=%CD%\src

echo.
echo  ============================================
echo   Queqq — Development Mode Tester
echo  ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv!
    echo Please run install.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" run.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  !! Queqq DEV crashed with exit code %ERRORLEVEL%
    echo  See log output above for details.
    echo.
    pause
)
