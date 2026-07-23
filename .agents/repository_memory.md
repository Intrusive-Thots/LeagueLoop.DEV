# Repository Memory

## Project Overview
- **Project**: LeagueLoop.DEV
- **Description**: Professional-grade League of Legends companion application providing automated champion select priority sniping, draft assistance, auto-rune page setup, arena synergy optimization, auto-honoring, and real-time match telemetry.
- **Repository Location**: `C:\Users\Administrator\LeagueLoop.DEV`
- **Remote Repository**: `https://github.com/Intrusive-Thots/LeagueLoop.DEV`

## Key Architecture & Frameworks
- **GUI Frameworks**: Dual support for CustomTkinter and PySide6 (Qt) in hybrid architecture mode.
- **Backend / LCU Connection**: Local LCU (League Client Update) WebSocket and HTTPS REST API polling via `lcu_driver` & `api_handler.py`.
- **Packaging**: PyInstaller ONEDIR mode + Inno Setup installer (`installer.iss`).

## Active Workspaces & Submodules
- `src/core/`: EventBus, AppState, ConfigManager, Logger, Security, Path utilities.
- `src/services/`: Automation engine, LCU service, Friend service, Champion service, Settings service, Window service, Theme service, Stats scraper.
- `src/ui/`: CustomTkinter pages/widgets, PySide6 Qt pages (`src/ui/qt/pages/`), QSS theme generator (`theme.py`), Header bar & dockable window manager.
- `LeagueLoopMobile/`: Capacitor + Vite cross-platform Android mobile app.
- `tests/`: Pytest suite (160+ unit & integration test cases).

## Recent Milestones & State
- All planned automation features (Priority Sniper, Draft Assistant, Arena Synergy V2, Auto-Honor) fully implemented and covered under test suite.
- PySide6 Qt main window shell with vector navigation sidebar, top control header bar, and dockable window support implemented.
- 9 Qt views (`AccountsPage`, `ChampionsPage`, `CoachPage`, `DashboardPage`, `FriendsPage`, `MatchPredictorPage`, `PatchNotesPage`, `PlayPage`, `SettingsPage`) verified and passing test suite.
