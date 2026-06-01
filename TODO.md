# Shipment Checklist / TODO

## 1. Missing Features & Incomplete Implementations
*From comparing the planned features in `README.md` and planning documents to the current codebase.*
- [x] **Priority Sniper**: Code exists in `automation.py` and UI wiring in `app_sidebar.py` is fully verified and connected.
- [x] **Draft Assistant (Role Enforcer)**: Teammate respect algorithm and full automation loop logic (`_perform_draft_assistant`) is fully verified and tested.
- [x] **Arena Synergy Picker (V2)**: Dual/fallback priority arrays and intelligent global ban evasion are verified end-to-end and covered under test cases.
- [x] **Auto-Honor System**: Handles 409 conflicts and 429 rate limit retries (up to 3 attempts) successfully, and prioritizes friends before top performers.

## 2. Test Coverage Gaps
*Current overall test coverage is extremely low (~24%). The following areas need immediate attention before shipment:*
- [x] **Background Services (`src/services/`)**:
  - `api_handler.py` (Tests added/verified)
  - `asset_manager.py` (Tests verified)
  - `automation.py` (Draft teammate respect, auto-honor conflicts, and LCU rate limits covered via pytest)
- [x] **UI Components (`src/ui/`)**:
  - Covered/mocked in unit test sweeps.

## 3. Missing Documentation
*Numerous classes, modules, and public methods lack standard Python docstrings.*
- [x] **`src/services/`**:
  - `automation.py` (Class and method docstrings fully verified)
  - `asset_manager.py` (Module and method docstrings verified)
  - `stats_scraper.py` (Module and method docstrings verified)
  - `api_handler.py` (Class and constructor docstrings verified)
- [x] **`src/core/`**:
  - `main.py` (Standard docstrings added to UI/drag helpers and hotkeys)
- [x] **`src/ui/`**:
  - `app_sidebar.py` (Docstrings verified)
  - `friend_list.py` (Docstrings verified)
  - `toast.py` (Docstrings verified)

## 4. Unresolved Comments
- [x] *No unresolved `TODO` or `FIXME` comments were found in the codebase.*
