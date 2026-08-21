# LeagueLoop UI/UX Overhaul — Task Tracker

## Milestone 1: Hybrid Architecture & Foundation
- [x] Create `src/core/event_bus.py` — Singleton EventBus for cross-service and UI events (using existing `events.py` EventBus)
- [x] Create `src/services/league_service.py` — Centralizes LCU state, connection, and events
- [x] Create `src/services/friend_service.py` — Fetches, models, and stores friends lists and statuses
- [x] Create `src/services/champion_service.py` — Manages champion metadata, DDragon icons, and local win rate caching
- [x] Create `src/services/settings_service.py` — Wraps `ConfigManager` configuration reads/writes with notifications
- [x] Create `src/core/state.py` — AppState and sub-states (using existing `state.py` AppState and State manager updates)
- [x] Create `src/ui/qt/theme.py` — PySide6 QSS generator using `design_tokens.json`
- [x] Setup `src/ui/qt/app_window.py` — Main PySide6 Window with Docked / Undocked modes support
- [x] Update `run.py` to support launching both CustomTkinter and PySide6 in hybrid mode using QTimer polling

## Milestone 2: Split app_sidebar.py
- [x] Extract sidebar layout logic to `src/ui/sidebar/sidebar.py`
- [x] Extract sidebar navigation to `src/ui/sidebar/navigation.py`
- [x] Extract status bar to `src/ui/sidebar/status_bar.py`
- [x] Reorganize CTk pages under `src/ui/pages/`
- [x] Create reusable widgets under `src/ui/widgets/`

## Milestone 3: PySide6 Views Implementation
- [x] Build PySide6 pages: Friends page, Champion select page, Accounts page, Settings page
- [x] Build PySide6 shells: Dashboard page, AI Coach page, Match predictor page, Patch notes page
