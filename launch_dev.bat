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

echo ================ LeagueLoop startup diagnostic ================ > "%LOG%"
echo Time: %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

REM Match ANY LeagueLoop-related process, not just python* - the packaged
REM build runs as LeagueLoop.exe and would otherwise be invisible here.
echo ---- LeagueLoop-related processes BEFORE launch ---- >> "%LOG%"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -or $_.Name -like 'LeagueLoop*' -or $_.CommandLine -like '*LeagueLoop*' -or $_.CommandLine -like '*run.py*' } | Select-Object ProcessId,Name,CommandLine | Format-List" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo ---- port 8337 (Local API) holder ---- >> "%LOG%"
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8337 -ErrorAction SilentlyContinue | Select-Object State,OwningProcess | Format-List" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo ---- launching app (unbuffered) ---- >> "%LOG%"
REM -u is essential: without it Python block-buffers stdout when redirected,
REM and every line is lost if the process is terminated rather than exiting.
".venv\Scripts\python.exe" -u run.py >> "%LOG%" 2>&1
set APPEXIT=%ERRORLEVEL%
echo. >> "%LOG%"
echo app_exit=%APPEXIT% >> "%LOG%"

echo. >> "%LOG%"
echo ---- LeagueLoop-related processes AFTER exit ---- >> "%LOG%"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -or $_.Name -like 'LeagueLoop*' -or $_.CommandLine -like '*LeagueLoop*' -or $_.CommandLine -like '*run.py*' } | Select-Object ProcessId,Name,CommandLine | Format-List" >> "%LOG%" 2>&1

echo.
type "%LOG%"

echo.
if "%APPEXIT%"=="15" (
    echo  ------------------------------------------------------------
    echo   Exit code 15 = this instance was TERMINATED, not crashed.
    echo   Something outside the app killed it ^(e.g. Task Manager, or
    echo   another copy started with --replace^).
    echo  ------------------------------------------------------------
) else if not "%APPEXIT%"=="0" (
    echo  !! LeagueLoop DEV exited with code %APPEXIT%
    echo  Full details: %LOG%
)
echo.
pause
