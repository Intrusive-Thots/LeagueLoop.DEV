@echo off
REM ============================================================
REM  Bring the repository in line with the source.
REM
REM  Claude can write files to this machine but cannot delete
REM  them, and the git remote is SSH, so these two steps have to
REM  happen here. Everything else is already on disk.
REM
REM  1. delete the Qt shell's leftover files
REM  2. drop user data from git tracking if it ever got added
REM  3. run the test suite
REM  4. commit and push, only if the suite is green
REM
REM  Read it before running it. Every path is listed explicitly;
REM  there are no wildcards that could match something else.
REM ============================================================
setlocal
cd /d "%~dp0.."

echo.
echo Tidying %CD%
echo.

REM --- the Qt shell ---------------------------------------------
if exist "src\ui\qt"                     rd /s /q "src\ui\qt"
if exist "run_qt.py"                     del /q "run_qt.py"
if exist "launch_qt_dev.bat"             del /q "launch_qt_dev.bat"
if exist "requirements-qt.txt"           del /q "requirements-qt.txt"
if exist "config\requirements-qt.txt"    del /q "config\requirements-qt.txt"

REM --- a service with no consumer once Qt is gone --------------
REM  client_window_tracker.py is NOT deleted. It was, and that broke
REM  docking: LeagueLoopApp.docking_loop imports it, so the thread died
REM  at startup and the window never moved or resized. It stays.

REM --- Qt-only tooling ----------------------------------------
if exist "tools\check_scaling.py"        del /q "tools\check_scaling.py"
if exist "tools\check_overflow.py"       del /q "tools\check_overflow.py"
if exist "tools\qt_visual_states.py"     del /q "tools\qt_visual_states.py"
if exist "tools\fix_desktop_shortcuts.ps1" del /q "tools\fix_desktop_shortcuts.ps1"

REM --- Qt-only tests ------------------------------------------
for %%F in (
    test_qt_ui.py
    test_qt_tabs.py
    test_qt_shell.py
    test_qt_champ_select.py
    test_qt_activity.py
    test_qt_accounts_tab.py
    test_qt_account_editor.py
    test_layout_fit.py
    test_window_states.py
    test_app_identity_and_popups.py
    test_client_window_tracking.py
    test_window_layer.py
    test_qt_new_tabs.py
    test_qt_stats_scraper.py
    test_qt_toast_and_tray.py
) do if exist "tests\%%F" del /q "tests\%%F"

REM --- docs about a migration that is over ---------------------
if exist "MIGRATION.md"                  del /q "MIGRATION.md"
if exist "CLEANUP.md"                    del /q "CLEANUP.md"
if exist "qt_startup.log"                del /q "qt_startup.log"

REM --- user data must never be tracked ------------------------
REM  These hold account credentials, settings and match history.
REM  They are ignored now, but `git rm --cached` is what removes
REM  one that was already added before the ignore rule existed.
REM  Errors here are expected and harmless when nothing is tracked.
for %%F in (accounts.json config.json leagueloop.db src\config.json) do (
    git ls-files --error-unmatch "%%F" >nul 2>&1 && git rm --cached -q "%%F"
)
if exist "sessions" git rm -r --cached -q "sessions" 2>nul

echo.
echo Running the test suite before committing...
echo.
REM  Output goes to a file as well as the screen. A failure here used to
REM  leave nothing behind to read: the window closed, the commit did not
REM  happen, and the reason was gone. tools\last_test_run.txt keeps it.
call ".venv\Scripts\python.exe" -m pytest -q > "tools\last_test_run.txt" 2>&1
set PYTEST_RC=%errorlevel%
type "tools\last_test_run.txt"
if not "%PYTEST_RC%"=="0" (
    echo.
    echo TESTS FAILED - nothing has been committed.
    echo Full output saved to tools\last_test_run.txt
    exit /b 1
)

echo.
echo Committing and pushing...
git add -A
git commit -F tools\commit_message.txt
git push

echo.
echo Done.
endlocal
