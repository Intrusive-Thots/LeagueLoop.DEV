@echo off
title LeagueLoop - Qt (PySide6)
cd /d "%~dp0"
set PYTHONPATH=%CD%\src
set QTLOG=%CD%\qt_startup.log

echo.
echo  ============================================
echo   LeagueLoop - Qt Shell (PySide6)
echo  ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv
    echo Run install.bat first.
    echo.
    pause
    exit /b 1
)

REM ---- Ensure PySide6 is present, installing it if not ----
".venv\Scripts\python.exe" -c "import PySide6" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  PySide6 is not installed yet - installing it now.
    echo  This is a one-time setup and takes a minute.
    echo.
    ".venv\Scripts\python.exe" -m pip install -r requirements-qt.txt
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo  !! Install failed. See the pip output above.
        echo.
        pause
        exit /b 1
    )
    echo.
    echo  PySide6 installed.
    echo.
)

REM ---- Launch, mirroring output to a log ----
REM -u keeps stdout unbuffered so nothing is lost if the process is killed.
echo ================ LeagueLoop Qt startup ================ > "%QTLOG%"
echo Time: %DATE% %TIME% >> "%QTLOG%"
echo. >> "%QTLOG%"

".venv\Scripts\python.exe" -u run_qt.py %* >> "%QTLOG%" 2>&1
set QTEXIT=%ERRORLEVEL%

echo. >> "%QTLOG%"
echo qt_exit=%QTEXIT% >> "%QTLOG%"

if %QTEXIT% NEQ 0 (
    echo.
    type "%QTLOG%"
    echo.
    echo  !! Qt shell exited with code %QTEXIT%
    echo  Full details: %QTLOG%
    echo.
    pause
)
