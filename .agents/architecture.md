# System Architecture

## Overview
LeagueLoop.DEV utilizes an event-driven service architecture with decoupled UI components operating across CustomTkinter and PySide6 Qt.

```
                  +--------------------------+
                  |  League Client (LCU API) |
                  +------------+-------------+
                               | WebSocket / REST
                               v
                  +--------------------------+
                  |   LeagueService & LCU    |
                  +------------+-------------+
                               | Events / Telemetry
                               v
                  +--------------------------+
                  |    Singleton EventBus    |
                  +-----+--------------+-----+
                        |              |
       +----------------+              +----------------+
       |                                                |
       v                                                v
+--------------+                                +---------------+
|  Automation  |                                |  UI Windows   |
|   Engine     |                                |  (Qt & CTk)   |
+--------------+                                +---------------+
```

## Layer Descriptions

### 1. Core Layer (`src/core/`)
- `events.py` / `event_bus.py`: Centralized pub/sub system handling event distribution between services and UI elements.
- `state.py`: Thread-safe application state container managing queue phase, selected champion, connected account, and user preferences.
- `config_manager.py`: Handles persistent JSON configuration loading, schema validation, and atomic writes to `config.json`.
- `security.py`: Secure storage and sanitization of LCU credentials and stored Riot tokens.

### 2. Service Layer (`src/services/`)
- `league_service.py`: Wraps LCU connection lifecycle, heartbeat checking, and client status event broadcasting.
- `automation/`: Sub-modules managing Champ Select priority sniping, draft assistance, skin equipping, rune page application, and auto-honoring.
- `friend_service.py`: Real-time LCU friend list monitoring, status updates, and invite management.
- `champion_service.py`: DataDragon asset caching, champion icon management, and win rate calculation integration.
- `stats_scraper.py`: Fetches match stats, win rates, and optimal rune builds from external endpoints.

### 3. UI Layer (`src/ui/`)
- **PySide6 Qt Shell (`src/ui/qt/`)**: Premium Riot-inspired UI featuring custom chromeless header bar, dark glassmorphic styling via `theme.py`, vector icon widgets, stacked page navigation, and dockable overlay support.
- **Pages**: Accounts, Champions, AI Coach, Dashboard, Friends, Match Predictor, Patch Notes, Play, Settings.
