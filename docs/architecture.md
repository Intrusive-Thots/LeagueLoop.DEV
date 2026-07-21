# LeagueLoop.DEV Architecture Guide

## Overview
LeagueLoop is an automated League of Legends LCU client companion built with a Python backend service layer and a PySide6 frameless desktop application shell.

```
                  ┌──────────────────────────────┐
                  │    LeagueLoop Application    │
                  └──────────────┬───────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
┌─────────────────┐                             ┌─────────────────┐
│  PySide6 GUI    │  ◄─── EventBus (Pub/Sub) ──►  │ Automation Loop │
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

### 1. Application Shell (`src/ui/qt/`)
- **Main Window**: `LeagueLoopQtWindow` in `app_window.py` provides custom frameless Riot window controls, custom snapping behavior via `WindowService`, vector sidebar navigation, and stacked pages.
- **Pages**:
  - `PlayPage`: Queue matchmaking controls, auto-accept toggles, manual client launcher button.
  - `DashboardPage`: Engine health diagnostics, system activity logs, and log directory button.
  - `ChampionsPage`: ARAM priority sniper list, role filter pills, search bar, and masteries.
  - `FriendsPage`: Friend list viewer with availability status, search filters, and party auto-join toggles.
  - `CoachPage`: AI Coach draft priority planner and live draft advisor.
  - `SettingsPage`: App preferences, lobby options, champ select automation, and hotkeys.
  - `AccountsPage`: Multi-account manager for saving Riot credentials and one-click account switching.

### 2. Service Layer (`src/services/`)
- `LeagueService`: Manages LCU lockfile discovery, HTTPS connections, and WebSocket subscription mapping.
- `AutomationEngine`: `src/services/automation/` modular gameflow phase handlers (`ready_check`, `champ_select`, `draft_assistant`, `chat_warden`, `dodge_requeue`, `end_game`, `friend_lobby`).
- `QueueService`: Manages queue searches, game lobbies, timers, and lobby recreation.
- `AccountManager`: Encrypted Riot credential storage and auto-login automation.
- `LocalAPIServer`: `src/services/api/` HTTP REST API server on port 8337 for mobile app and remote control.

### 3. Event Bus & Logger (`src/core/events.py`, `src/utils/logger.py`)
- Thread-safe `EventBus` handles asynchronous decoupled messaging across UI, service loops, and LCU WebSockets.
- `Logger` manages rotating file logging (`debug.log`, `error.log`), global `sys.excepthook`, `threading.excepthook`, and `faulthandler`.
