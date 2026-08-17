# LeagueLoop.DEV Changelog

All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.08.141] - 2026-08-16

- **Feature / Hardening**: Added `src/utils/riot_id.py` with `resolve_riot_id()` / `resolve_riot_id_lower()` as the single source of truth for name resolution (RIOT-ID-001).
- Updated `friend_list.py` and `local_api.py` to use the utility instead of ad-hoc field fallbacks.
- Added unit tests in `tests/test_riot_id.py`.


## [1.08.140] - 2026-08-16

- **Docs**: Synced CHANGELOG with current health score 90/100 and next focus from improvement_plan.
- **Version**: Bumped to 1-08-137-1902.

## [1.08.139] - 2026-08-16

- **Docs**: Bumped improvement_plan.md health to 90/100, clarified next focus (PySide6 migration, asset_manager modularization, SQLite, telemetry prune, LCU hardening).
- **Docs**: Refreshed TASK_QUEUE.md.

## [1.08.138] - 2026-08-16

- **Fix**: Restored full `LeagueLoopApp` implementation in `src/core/main.py` (was replaced by a placeholder in the prior DI commit).
- Wired `ApplicationContainer` correctly: services constructed via container, shutdown routes through `container.shutdown()`.
- App is runnable again; DI skeleton remains intact for future lifecycle extraction.

## [1.08.137] - 2026-08-16

- **ApplicationContainer**: Introduced `src/core/container.py` as the first step toward DI. Core services (ConfigManager, AssetManager, LCUClient, StatsScraper, AutomationEngine, AccountManager) are now constructed via the container instead of directly inside `LeagueLoopApp.__init__`.
- Prepares for Application lifecycle extraction and reduced coupling (improvement_plan Phase 2/3).

## [1.08.149] - 2026-08-07

- Prior telemetry and pooling work retained.
