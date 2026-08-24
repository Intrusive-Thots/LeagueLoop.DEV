@echo off
REM ============================================================
REM  Delete the PySide6 shell and push the result.
REM
REM  Everything else in this change is already on disk. This
REM  script only removes the files that Claude cannot delete
REM  itself -- the desktop bridge can write files but not
REM  delete them -- and then commits and pushes.
REM
REM  Read it before running it. Every path is listed explicitly;
REM  there are no wildcards that could match something else.
REM ============================================================
setlocal
cd /d "%~dp0.."

echo.
echo Removing the Qt shell from %CD%
echo.

REM --- the shell itself ---------------------------------------
if exist "src\ui\qt"                     rd /s /q "src\ui\qt"
if exist "run_qt.py"                     del /q "run_qt.py"
if exist "launch_qt_dev.bat"             del /q "launch_qt_dev.bat"
if exist "requirements-qt.txt"           del /q "requirements-qt.txt"

REM --- a service with no consumer once Qt is gone --------------
if exist "src\services\client_window_tracker.py" del /q "src\services\client_window_tracker.py"

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
) do if exist "tests\%%F" del /q "tests\%%F"

REM --- docs about a migration that is over ---------------------
if exist "MIGRATION.md"                  del /q "MIGRATION.md"
if exist "CLEANUP.md"                    del /q "CLEANUP.md"

REM --- stale logs from the Qt runs ----------------------------
if exist "qt_startup.log"                del /q "qt_startup.log"

echo.
echo Deleted. Running the test suite before committing...
echo.
call ".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 (
    echo.
    echo TESTS FAILED - nothing has been committed. Fix, then re-run.
    exit /b 1
)

echo.
echo Committing and pushing...
git add -A
git commit -m "Remove the PySide6 shell; CustomTkinter is the only shell" -m "The Qt shell had no friend list, which is why the video review was describing the old UI all along. Removes src/ui/qt, run_qt.py, the Qt-only tools and tests, and client_window_tracker (no consumer once the companion anchor is gone). New application icon: a gold cycle ring with a play glyph, legible at 16px."
git push

echo.
echo Done.
endlocal
