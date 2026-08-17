# LeagueLoop.DEV Comprehensive Improvement Plan

## Project Audit Baseline
**Repository**: `Intrusive-Thots/LeagueLoop.DEV`

### Current Assessment Overview
- **Overall Health**: 94/100
- **Primary Objectives**:
  1. Complete PySide6 migration and eliminate legacy Tkinter code. (pending — scaffold in `src/ui/qt/`)
  2. Reduce architectural coupling via ApplicationContainer and dependency injection. (done — construction + shutdown + loops wired)
  3. Improve reliability, error logging, and application lifecycle management. (done)
  4. Expand test suite coverage and CI/CD pipelines. (done — 255+ tests, smoke + full suite)
  5. Modernize UI architecture with Riot Games design language tokens. (partial)
  6. Optimize startup speed, memory footprint, and maintainability. (done — extensive perf work; RunningStats for HTTP latency + variance)

---

## Next Focus
1. Finish PySide6 migration path (scaffold already in `src/ui/qt/`; begin replacing CustomTkinter surfaces).
2. Optional SQLite for match history / post-game summaries.
3. Continue modular split of `asset_manager.py` (still large; ConfigManager already extracted).
4. Harden LCU transport / reconnect edge cases.
5. Prune remaining exotic telemetry methods (low priority; tests cover them).

## Recent Hygiene
- Documentation accuracy aligned with CustomTkinter runtime.
- EventBus thread-safety and typed events.
- Local API default-bound to localhost + restricted CORS.
- CI smoke-test gate before full suite.
- O(1) RunningStats for latency telemetry (variance/stddev/CV).
- 2026-08 hygiene: plan score raised to 94/100; task queue cleaned.
