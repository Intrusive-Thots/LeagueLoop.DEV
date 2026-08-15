# LeagueLoop.DEV Architecture Guide

## Overview
LeagueLoop is an automated League of Legends LCU client companion built with a Python backend service layer and a **CustomTkinter** desktop application shell.

> **Note**: This document describes the **current runtime architecture**. For the planned PySide6 migration, see [Target Architecture](#target-architecture-pyside6-migration).

```
                  ┌──────────────────────────────┐
                  │    LeagueLoop Application    │
                  └──────────────┬───────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
┌─────────────────┐                             ┌─────────────────┐
│ CustomTkinter   │  ◄─── EventBus (Pub/Sub) ──►  │ Automation Loop │
│ (Window Shell)  │                             │ (Engine Services)│
└────────┬────────┘                             └────────┬────────┘
         │                                               │
         └───────────────────────┬───────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │  LCU REST & WebSocket   │
                    │   (League Client API)   │
                    └─────────────────────────┘
```

## Layer Definitions

### 1. Application Shell (`src/ui/`)
- **Main Window**: `LeagueLoopApp` in `src/core/main.py` provides a borderless CustomTkinter window with Win32 docking behavior, sidebar navigation, and stacked content areas.
- **UI Components**:
  - `SidebarWidget` (`src/ui/app_sidebar.py`): Navigation, queue controls, auto-accept toggles, power state.
  - `MiniPlayer` (`src/ui/components/mini_player.py`): Compact "Orb" mode for draft/in-game overlay.
  - **Tools** (`src/ui/components/game_tools/`): Draft tool, arena tool, accounts tool, loot tool.
  - **Feedback** (`src/ui/components/feedback/`): Activity logs, status badges, toast notifications.
  - **Components** (`src/ui/components/`): Champion input, draggable lists, priority grids, settings panels, tooltips.

### 2. Service Layer (`src/services/`)
- `LCUClient` (`api_handler.py`): Manages LCU lockfile discovery, HTTPS connections, and WebSocket subscriptions.
- `AutomationEngine` (`src/services/automation.py`): Gameflow phase handlers for ready_check, champ_select, draft_assistant, chat_warden, dodge_requeue, end_game, friend_lobby.
- `AccountManager`: Encrypted Riot credential storage and auto-login automation.
- `StatsScraper`: Fetches summoner stats, ranked info, and match history.
- `LocalAPIHandler` (`local_api.py`): HTTP REST API server on port 8337 for mobile companion and remote control.

### 3. Event Bus & Logger (`src/core/events.py`, `src/utils/logger.py`)
- Thread-safe `EventBus` handles asynchronous decoupled messaging across UI, service loops, and LCU WebSockets.
- `Logger` manages rotating file logging (`debug.log`, `error.log`), global `sys.excepthook`, `threading.excepthook`, and `faulthandler`.

---

## Target Architecture (PySide6 Migration)

> **Status**: Planned future state. Do not implement against this structure until the migration is complete.

The planned PySide6 migration will move the UI layer to `src/ui/qt/` with the following structure:

- **Main Window**: `LeagueLoopQtWindow` with frameless Riot-styled window controls
- **Pages**: `PlayPage`, `DashboardPage`, `ChampionsPage`, `FriendsPage`, `CoachPage`, `SettingsPage`, `AccountsPage`
- **Theme**: Design tokens matching Riot Games visual language

This migration aims to improve performance, modernize the UI, and reduce dependency on Tkinter-based components. See `docs/improvement_plan.md` Phase 1 for details.
