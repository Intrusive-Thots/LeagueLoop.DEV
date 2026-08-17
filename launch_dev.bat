@echo off
title LeagueLoop - DEV Tester
cd /d "%~dp0"
set PYTHONPATH=%CD%\src
set LOG=%CD%\startup_diagnostic.log

echo.
echo  ============================================
echo   LeagueLoop - Development Mode Tester
echo  ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv!
    echo Please run install.bat first.
    pause
    exit /b 1
)

REM ---- capture a full startup diagnostic to startup_diagnostic.log ----
echo ================ LeagueLoop startup diagnostic ================ > "%LOG%"
echo Time: %DATE% %TIME% >> "%LOG%"
echo CWD : %CD% >> "%LOG%"
echo. >> "%LOG%"

echo ---- python processes BEFORE launch ---- >> "%LOG%"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | Format-List" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo ---- interpreter ---- >> "%LOG%"
".venv\Scripts\python.exe" -V >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo ---- import smoke test (no app start) ---- >> "%LOG%"
".venv\Scripts\python.exe" -c "import sys; sys.path.insert(0,'src'); import core.main; print('core.main imported OK')" >> "%LOG%" 2>&1
echo import_exit=%ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo ---- launching app ---- >> "%LOG%"
".venv\Scripts\python.exe" run.py >> "%LOG%" 2>&1
set APPEXIT=%ERRORLEVEL%
echo. >> "%LOG%"
echo app_exit=%APPEXIT% >> "%LOG%"

echo. >> "%LOG%"
echo ---- python processes AFTER exit ---- >> "%LOG%"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | Format-List" >> "%LOG%" 2>&1

REM ---- show it on screen too ----
echo.
type "%LOG%"

echo.
if %APPEXIT% NEQ 0 (
    echo  !! LeagueLoop DEV exited with code %APPEXIT%
    echo  Full details saved to: %LOG%
    echo.
)
pause
