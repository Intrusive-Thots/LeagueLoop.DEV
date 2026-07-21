# LeagueLoop.DEV Comprehensive Improvement Plan

## Project Audit Baseline
**Repository**: `Intrusive-Thots/LeagueLoop.DEV`

### Current Assessment Overview
- **Overall Health**: 58/100
- **Primary Objectives**:
  1. Complete PySide6 migration and eliminate legacy Tkinter code.
  2. Reduce architectural coupling via ApplicationContainer and dependency injection.
  3. Improve reliability, error logging, and application lifecycle management.
  4. Expand test suite coverage and CI/CD pipelines.
  5. Modernize UI architecture with Riot Games design language tokens.
  6. Optimize startup speed, memory footprint, and maintainability.

---

## Phase Breakdown

### PHASE 0 — DOCUMENTATION AND REPOSITORY CLEANUP
**Priority**: HIGH
- Rewrite `README.md` around the current PySide6 architecture.
- Add structured documentation:
  - `docs/architecture.md`
  - `docs/development.md`
  - `docs/troubleshooting.md`
  - `docs/roadmap.md`

### PHASE 1 — COMPLETE PYQT/PYSIDE6 MIGRATION
**Priority**: CRITICAL
- Inventory and remove remaining legacy Tkinter/CustomTkinter widgets.
- Ensure all pages use pure PySide6 layouts and signals/slots.
- Target UI structure: `src/ui/qt/` (`pages/`, `widgets/`, `theme/`).

### PHASE 2 — APPLICATION LIFECYCLE REFACTOR
**Priority**: HIGH
- Introduce `ApplicationManager` to decouple startup/shutdown responsibilities:
  - `startup()`
  - `shutdown()`
  - Service initialization & dependency lifecycle

### PHASE 3 — REMOVE GLOBAL SINGLETON OVERUSE
**Priority**: HIGH
- Introduce `ApplicationContainer` for explicit dependency injection:
  - `SettingsService`
  - `AssetManager`
  - `LCUClient`
  - `Logger`
  - `EventManager`

### PHASE 4 — EVENT SYSTEM IMPROVEMENT
**Priority**: MEDIUM
- Enhance `EventBus` into a typed event dispatch system with subscription handle cleanup and thread safety.

### PHASE 5 — RIOT LCU CLIENT HARDENING
**Priority**: HIGH
- Introduce `LCUTransport` wrapper:
  - Isolated certificate & lockfile handling
  - Exponential backoff & reconnect manager
  - Connection status event notifications

### PHASE 6 — ASSET SYSTEM OPTIMIZATION
**Priority**: MEDIUM
- Cache versioning, checksum validation, expiration rules, and parallel batch downloads.
- Structure: `cache/champions/`, `cache/items/`, `cache/skins/`, `cache/metadata/`.

### PHASE 7 — UI/UX MODERNIZATION
**Priority**: HIGH
- Riot Games visual design tokens (`spacing: 4, 8, 12, 16, 24`).
- Glassmorphic card frames, vector icon painters, animated hover states, acrylic blur backdrops.

### PHASE 8 — STATE MANAGEMENT
**Priority**: HIGH
- Centralized `ApplicationState` model for champion picks, game phases, settings, and LCU status.

### PHASE 9 — TESTING SYSTEM
**Priority**: CRITICAL
- Maintain 100% test pass rate across unit, integration, and UI component tests in `tests/`.

### PHASE 10 — CI/CD AUTOMATION
**Priority**: HIGH
- GitHub Actions pipeline: linting, pytest suite, executable build, and release packaging.

### PHASE 11 — ERROR HANDLING AND LOGGING
**Priority**: HIGH
- Structured logging, global exception hooks (`sys.excepthook`, `threading.excepthook`), crash reports, and rotating `debug.log`/`error.log`.

### PHASE 12 — SECURITY REVIEW
**Priority**: MEDIUM
- Dependency security audit, encrypted credential storage in `AccountManager`, secret scanning.

### PHASE 13 — PERFORMANCE OPTIMIZATION
**Priority**: MEDIUM
- Lazy page loading, async background workers, image sprite caching. Target startup under 3 seconds.

### PHASE 14 — DATABASE LAYER
**Priority**: MEDIUM
- Optional SQLite database storage for match history, stats caching, and champion mastery data.

### PHASE 15 — PLUGIN ARCHITECTURE
**Priority**: LOW/MEDIUM
- Plugin extension framework (`plugins/`) with `plugin.json` manifest for custom tools.

---

## Implementation Sprints

- **Sprint 1**: Documentation cleanup, PySide6 migration completion, dependency pruning.
- **Sprint 2**: Lifecycle manager, dependency container, typed events.
- **Sprint 3**: LCU transport hardening, asset system optimization, state manager.
- **Sprint 4**: UI redesign, design tokens, micro-animations.
- **Sprint 5**: Testing expansion, CI/CD pipeline, installer packaging.
- **Sprint 6**: SQLite database layer, plugin architecture.
