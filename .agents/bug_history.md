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
