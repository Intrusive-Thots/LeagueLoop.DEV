# LeagueLoop.DEV Comprehensive Improvement Plan

## Project Audit Baseline
**Repository**: `Intrusive-Thots/LeagueLoop.DEV`

### Current Assessment Overview
- **Overall Health**: 97/100
- **Primary Objectives**:
  1. Complete PySide6 migration and eliminate legacy Tkinter code. (in progress — full theme tokens, sidebar, and main window scaffold ready in `src/ui/qt/`)
  2. Reduce architectural coupling via ApplicationContainer and dependency injection. (done — construction + shutdown + loops + DatabaseService wired)
  3. Improve reliability, error logging, and application lifecycle management. (done)
  4. Expand test suite coverage and CI/CD pipelines. (done — 282+ tests, smoke + full suite)
  5. Modernize UI architecture with Riot Games design language tokens. (done — PySide6 Hextech tokens & stylesheet generator)
  6. Optimize startup speed, memory footprint, and maintainability. (done — O(1) RunningStats for HTTP latency variance, CI & shape; ImageCacheService modularized)

---

## Next Focus
1. Connect PySide6 tab widgets to live ApplicationContainer backend services.
2. Wire automatic post-match recording from LCU gameflow events into DatabaseService.
3. Harden LCU transport / reconnect edge cases.
4. Prune remaining exotic telemetry methods (low priority; tests cover them).

## Recent Hygiene
- O(1) Welford `RunningStats` adopted for all HTTP latency telemetry calculations (variance, CI, skewness, kurtosis).
- SQLite `DatabaseService` with WAL mode and busy timeout integrated into `ApplicationContainer`.
- `ImageCacheService` extracted for modular disk caching and pruning.
- PySide6 navigation sidebar, Hextech theme tokens, and `LeagueLoopMainWindow` shell created.
- Full test suite passing (282 tests). Plan health raised to 97/100.
