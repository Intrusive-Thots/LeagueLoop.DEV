# LeagueLoop.DEV Comprehensive Improvement Plan

## Project Audit Baseline
**Repository**: `Intrusive-Thots/LeagueLoop.DEV`

### Current Assessment Overview
- **Overall Health**: 86/100 (up from 85)
- **Primary Objectives**:
  1. Complete PySide6 migration and eliminate legacy Tkinter code. (pending)
  2. Reduce architectural coupling via ApplicationContainer and dependency injection. (done — construction + shutdown + loops wired)
  3. Improve reliability, error logging, and application lifecycle management. (done)
  4. Expand test suite coverage and CI/CD pipelines. (done — 255+ tests)
  5. Modernize UI architecture with Riot Games design language tokens. (partial)
  6. Optimize startup speed, memory footprint, and maintainability. (done — extensive perf work; RunningStats adopted for HTTP latency)

---

## Next Focus
1. ~~ApplicationContainer wired into LeagueLoopApp (construction + shutdown). Full lifecycle extraction next.~~ **Done**
2. Finish PySide6 migration path (scaffold already in `src/ui/qt/`).
3. Optional SQLite for match history.
4. ~~Reduce excessive telemetry methods in `api_handler.py` by adopting `src/utils/running_stats.RunningStats` (Welford online)~~ **Done for primary HTTP latency path** — remaining exotic jitter polarization methods can be pruned later.
