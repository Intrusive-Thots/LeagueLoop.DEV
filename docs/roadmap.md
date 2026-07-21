# LeagueLoop.DEV Feature Roadmap

## Completed Milestones
- [x] PySide6 Frameless GUI Migration with Riot design tokens.
- [x] Multi-Account Manager (`AccountsPage`) with one-click credential login.
- [x] Manual Riot/League Client Launcher & Auto-Launcher engine loop.
- [x] Global Exception Logging (`sys.excepthook`, `threading.excepthook`, `error.log`).
- [x] 100% PyTest Suite Coverage (26 test files passing).

## Near-Term Roadmap
- [ ] **Sprint 1**: Deprecate remaining CustomTkinter code completely.
- [ ] **Sprint 2**: Refactor lifecycle management via `ApplicationManager` and dependency injection (`ApplicationContainer`).
- [ ] **Sprint 3**: `LCUTransport` wrapper with exponential backoff and reconnect handles.
- [ ] **Sprint 4**: Expanded UI animations, micro-interactions, and visual polish.
- [ ] **Sprint 5**: CI/CD pipeline automation with GitHub Actions.
- [ ] **Sprint 6**: SQLite database layer for match stats history.
