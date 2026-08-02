# Bug History & Resolutions

## Resolved Issues

### 1. Auto-Honor LCU Conflict (409 / 429 Rate Limits)
- **Issue**: LCU endpoints returned HTTP 409 Conflict during game transition phases or 429 Too Many Requests during rapid automated API calls.
- **Fix**: Added exponential backoff retry loop (up to 3 retries) with state checking in `automation.py` before executing auto-honor calls.

### 2. PySide6 Headless Test Failures
- **Issue**: PySide6 widget instantiation tests failed in headless environments when `QApplication` instance was absent.
- **Fix**: Implemented singleton fallback check `QApplication.instance() or QApplication([])` in `tests/test_pyside6_pages.py`.

### 3. Queue Mode Selection & Lock-In Lag
- **Issue**: High-latency LCU RPC calls blocked GUI main thread during Champ Select phase events.
- **Fix**: Offloaded LCU RPC polling and event handlers to worker threads connected asynchronously to `EventBus`.

### 4. Icon Asset Pre-caching Null Reference
- **Issue**: Missing champion icon files caused rendering exceptions on cold boot.
- **Fix**: Added fallback default icon rendering in `asset_manager.py` and auto-download from DataDragon CDN on asset cache miss.

### 5. Acrylic Blur NameError Bug
- **Issue**: `apply_acrylic_blur` referenced `tk_window` instead of the `window` function parameter, which raised a `NameError` on execution.
- **Fix**: Updated `_get_hwnd(window)` call to match function parameter name and added platform check for Win32 `creationflags`.

### 6. Qt Theme Compiler Function Alias Missing
- **Issue**: `focus_states.py` attempted to import `get_color` from `ui.qt.theme`, but only `get_theme_color` was defined.
- **Fix**: Added `get_color = get_theme_color` alias to `src/ui/qt/theme.py`.

---

## Session 2026-07-25/26 — Recurring Bug Classes

### Cross-Thread PySide6 GUI Violations (Fixed 5 files, recurred twice)
- **Symptom**: Application freezes, locked event loop, Shiboken crashes
- **Root Cause**: `AssetManager.get_icon_async` executed image callbacks on background `threading.Thread` workers. Callbacks created `QPixmap` and called `set_pixmap()` directly on Qt widgets from non-GUI threads.
- **Fix**: Added `_safe_callback` wrapper in `asset_manager.py` that checks `QThread.currentThread() != app.thread()` and uses `QTimer.singleShot(0, ...)` to marshal to main thread. Updated all icon loading callbacks in `champions_page.py`, `champion_cell.py`, `friends_page.py`, `friend_row.py`.
- **Prevention**: Architecture constraint THREAD-001, regression tests in `test_regression_guards.py::TestThreadSafety`

### Riot ID Name Resolution Fragmentation (Fixed 6 files, recurred twice)
- **Symptom**: Friends list shows blank names, summoner name shows empty, FriendCard skips friends
- **Root Cause**: LCU migrated to Riot IDs (`gameName#gameTag`), leaving legacy `name`/`displayName` empty. Each UI file implemented its own fallback chain with different field orderings.
- **Fix**: Created centralized `utils/riot_id.py` with `resolve_riot_id()` function. Replaced all inline resolution across `friend_service.py`, `friend_row.py`, `friends_page.py`, `play_viewmodel.py`, `header_viewmodel.py`, `dodge_requeue.py`.
- **Prevention**: Architecture constraint RIOT-ID-001, regression tests in `test_regression_guards.py::TestRiotIdResolution`

### LCU Process Scanner Premature Match (Fixed across sessions)
- **Symptom**: App fails to connect to LCU despite League Client running
- **Root Cause**: `scan_clients()` matched `LeagueClient.exe` (parent launcher, no credentials) and set `league_found = True` without checking for `--app-port`/`--remoting-auth-token`. Never scanned `LeagueClientUx.exe` which has the actual credentials.
- **Fix**: Only set `league_found = True` when both port AND token are extracted from process cmdline.
- **Prevention**: Architecture constraint LCU-001, regression tests in `test_regression_guards.py::TestLCUProcessScanner`

### Batch Render Layout Thrashing (Fixed 2 files, recurred twice)
- **Symptom**: UI freezes for 2-3 seconds when navigating to Champions or Friends page
- **Root Cause**: Inserting 65-170+ widgets individually triggers layout recalculation for each widget.
- **Fix**: Wrapped batch insertion loops in `setUpdatesEnabled(False)` ... `finally: setUpdatesEnabled(True)` in `champions_page.py` and `friends_page.py`.
- **Prevention**: Architecture constraint RENDER-001, regression tests in `test_regression_guards.py::TestBatchRendering`
