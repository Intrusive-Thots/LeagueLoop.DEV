# LeagueLoop File Index

This document provides a high-level overview of the major files in the repository and their responsibilities.

## `src/core/`
The backbone of the application running the event loop and initializing subsystems.
- **`main.py`**: The main `LeagueLoopApp` class. Initializes the UI and binds the `AutomationEngine`.
- **`constants.py`**: Application-wide constants, file paths, versions, and generic settings.
- **`version.py`**: A single source of truth for the application version.

## `src/services/`
Background workers and logic operators communicating with local APIs and the internet.
- **`api_handler.py`**: Handles direct HTTP REST calls to the League Client (LCU).
- **`automation.py`**: The `AutomationEngine` class. Monitors client states (e.g., Matchmaking, Champ Select) and executes automated actions.
- **`asset_manager.py`**: Fetches and caches DDragon assets (Champion icons, spell icons).
- **`stats_scraper.py`**: Scrapes external analytic sites for champion win rates and stats.

## `src/ui/`
The CustomTkinter interface. Separated into views, components, and layout.
- **`app_sidebar.py`**: The main navigation toggle sidebar on the left side of the window.
- **`components/`**: Reusable generic widgets.
  - `priority_grid.py`: The drag-and-drop champion priority list.
  - `friend_list.py`: The friend invite/auto-join UI.
  - `hotkey_recorder.py`: Keyboard shortcut capture widget for the Advanced settings tab.
  - `toast.py`: Temporary notification popups.
- **`layout/`**: Structural containers.
  - `page_container.py`: Wraps standard pages.
  - `section_container.py`: Handles inner padded blocks.

## `src/utils/`
Stateless utility functions.
- **`logger.py`**: Configures the `debug.log` and `error.log` output.
- **`path_utils.py`**: Calculates safe absolute paths for assets, whether running from source or within a PyInstaller bundle.

## Root Directories & Scripts
- **`build.bat`**: Uses PyInstaller and `LeagueLoop.spec` to build `dist/LeagueLoop.exe`.
- **`launch_dev.bat`**: Dev script to launch the app locally with correct `PYTHONPATH`.
- **`run.py`**: Python entry point. Appends `src/` to `sys.path`.
- **`installer.iss`**: Inno Setup script used to generate an installer from the build output.
- **`tests/`**: Unit test suite for verifying individual modules.
