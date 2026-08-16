# LeagueLoop.DEV Comprehensive Improvement Plan

## Project Audit Baseline
**Repository**: `Intrusive-Thots/LeagueLoop.DEV`

### Current Assessment Overview
- **Overall Health**: 90/100 (up from 88)
- **Primary Objectives**:
  1. Complete PySide6 migration and eliminate legacy Tkinter code. (pending — scaffold in `src/ui/qt/`)
  2. Reduce architectural coupling via ApplicationContainer and dependency injection. (done — construction + shutdown + loops wired)
  3. Improve reliability, error logging, and application lifecycle management. (done)
  4. Expand test suite coverage and CI/CD pipelines. (done — 255+ tests, smoke + full suite)
  5. Modernize UI architecture with Riot Games design language tokens. (partial)
  6. Optimize startup speed, memory footprint, and maintainability. (done — extensive perf work; RunningStats for HTTP latency)

---

## Next Focus
1. Finish PySide6 migration path (scaffold already in `src/ui/qt/`; begin replacing CustomTkinter surfaces).
2. Optional SQLite for match history / post-game summaries.
3. Prune remaining exotic jitter polarization telemetry methods in `api_handler.py` (low priority; tests cover them).
4. Continue modular split of `asset_manager.py` (currently ~6k LOC).
5. Harden LCU transport / reconnect edge cases.
