# LeagueLoop Engineering Baseline Report

**Repository**: `Intrusive-Thots/LeagueLoop.DEV`  
**Generated At**: `2026-08-17`  
**Git Branch**: `master`  
**Commit Baseline**: `db5e4d9`  
**Python Runtime**: `3.12.10 (win32)`

---

## 1. Performance & Resource Baselines

| Metric | Measured Baseline | Target Budget | Status |
| :--- | :--- | :--- | :--- |
| **Container Cold Import Duration** | ~710 ms (`api_handler`: ~308ms, `automation`: ~179ms, `qt_ui`: ~203ms) | < 1,000 ms |  HEALTHY |
| **Container Initialization Memory (RSS)** | 47.97 MB (includes DDragon & Meraki asset lookup maps) | < 65 MB |  HEALTHY |
| **Idle Memory Overhead** | 17.43 MB initial base process | < 25 MB |  HEALTHY |
| **Full Test Suite Execution Duration** | 2.10 seconds (286 tests) | < 4.00 seconds |  OPTIMIZED |
| **LCU Transport Latency Calculation Overhead** | $O(1)$ Welford online algorithm (`RunningStats`) | $O(1)$ |  OPTIMIZED |
| **Disk Cache Scan Latency** | < 0.5 ms (TTL cached at 3.0s) | < 5.0 ms |  OPTIMIZED |

---

## 2. Codebase Landscape & Scale

### Modules Over 1,000 Lines
1. `src/services/asset_manager.py` — **5,840 lines** (Contains DDragon loaders, Meraki parsing, slice pool recyclers, recommendation search methods)
2. `src/services/api_handler.py` — **3,293 lines** (Contains LCU connection loops, rate limiting, request diagnostics, telemetry methods)
3. `src/ui/app_sidebar.py` — **1,673 lines** (Legacy CustomTkinter navigation sidebar)
4. `src/services/automation.py` — **1,620 lines** (Automation engine loop, champ select, auto-accept, role detection, auto-honor)
5. `src/ui/components/priority_grid.py` — **1,564 lines** (CustomTkinter champion priority grid)

### Architecture Highlights & Recent Additions
- **ApplicationContainer**: Central dependency injection container managing service lifecycles (`lcu`, `assets`, `config`, `db`, `scraper`, `automation`, `account_manager`).
- **DatabaseService**: Thread-safe SQLite persistence with WAL journal mode (`PRAGMA journal_mode = WAL;`) and busy timeout for matches and telemetry snapshots.
- **ImageCacheService**: Standalone disk cache scanner with TTL caching and automated LRU/size-based pruning.
- **PySide6 UI Foundation**: Hextech design tokens (`theme.py`), navigation sidebar, frameless titlebar, and initial tab views (`QtPlayTab`, `QtDiagnosticsTab`, `QtSettingsTab`).

---

## 3. Test Suite Health

- **Total Test Cases**: 286
- **Test Duration**: 2.10s
- **Pass Rate**: 100% (286/286 passing)
- **Coverage Highlights**:
  - `test_api_handler.py` (48 tests)
  - `test_asset_manager.py` (61 tests)
  - `test_automation.py` (38 tests)
  - `test_database.py` (5 tests)
  - `test_qt_tabs.py` (3 tests)
  - `test_qt_ui.py` (3 tests)
  - `test_ws_telemetry.py` (29 tests)

---

## 4. Identified Technical Debt & Migration Priorities

1. **LCU Connection State Machine (Phase 2)**:
   - Convert disparate boolean flags (`is_connected`, `reconnecting`, `_connection_lost`) into a unified `ConnectionState` finite state machine (`DISCONNECTED`, `DISCOVERING`, `CONNECTING`, `CONNECTED`, `RECONNECTING`).
2. **Immutable Central Application State & Typed Events (Phases 1 & 3)**:
   - Introduce central state models (`ClientState`, `GameflowState`, `ChampSelectState`, `AutomationState`) observed by presentation layer without direct service querying.
3. **Champion Priority Decision Engine (Phase 5)**:
   - Modularize draft decisions into `src/services/draft/` (`priority_engine.py`, `role_detector.py`, `pick_strategy.py`, `ban_strategy.py`).
4. **PySide6 Native Migration (Phase 7)**:
   - Expand `src/ui/qt/` with tokenized design system (`colors`, `typography`, `spacing`), virtualized champion grid, and pages (`Play`, `Automation`, `Profile`, `Settings`), paving the way to retire legacy CustomTkinter.
