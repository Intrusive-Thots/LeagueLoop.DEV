# LeagueLoop File Index

This document provides a high-level overview of the major files in the repository, their responsibilities, and their dependencies.

## 📁 `src/core/`
The backbone of the application running the event loop, state single-source-of-truth, and initializing subsystems.
- **[`constants.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/core/constants.py)**: Application-wide constants, file paths, versions, and generic settings.
- **[`events.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/core/events.py)**: Central event bus (`EventBus` singleton) for thread-safe cross-component communication.
- **[`main.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/core/main.py)**: The main `LeagueLoopApp` class. Initializes the UI framework and binds the `AutomationEngine`.
- **[`state.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/core/state.py)**: Single source of truth application-wide state (`State` singleton).
- **[`state_manager.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/core/state_manager.py)**: Event listener that updates `State` dynamically based on LCU API events, eliminating polling stutters.
- **[`version.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/core/version.py)**: Single source of truth for the application version.

## 📁 `src/services/`
Background workers and logic operators communicating with local APIs and the internet.
- **[`account_manager.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/services/account_manager.py)**: Securely stores Riot account credentials using Windows DPAPI (CryptProtectData) and manages automatic logins via Riot Client's API.
- **[`api_handler.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/services/api_handler.py)**: Handles direct HTTPS REST calls, session headers, and certificate management for the League Client (LCU).
- **[`asset_manager.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/services/asset_manager.py)**: Fetches and caches Riot Data Dragon assets (champion/spell icons) and Meraki Analytics role/position assignments.
- **[`automation.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/services/automation.py)**: The `AutomationEngine`. Monitors the LCU client status, handling auto-accept, bans, and champion select auto-picks.
- **[`discord_rpc.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/services/discord_rpc.py)**: Manages Discord Rich Presence status reflecting active gameflow queue phases in real-time.
- **[`local_api.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/services/local_api.py)**: Exposes a local HTTP server allowing the mobile companion app to query stats, view lobby state, swap bench champs, and toggle remote configs.
- **[`stats_scraper.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/services/stats_scraper.py)**: Scrapes external champion analytics data (e.g., win rates and synergy recommendations).

## 📁 `src/ui/`
The CustomTkinter interface. Separated into views, components, and layout.
- **[`app_sidebar.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/app_sidebar.py)**: The main navigation layout showing control toggles and stats panels.
- **[`ui_shared.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/ui_shared.py)**: Consolidates imports and exports for colors, fonts, hover animations, and custom widgets.
- **📁 `components/`**: Reusable generic widgets.
  - **[`about_page.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/about_page.py)**: The "About" screen containing author info, licenses, and easter eggs.
  - **[`champion_input.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/champion_input.py)**: Champion selection search box with autocomplete filters.
  - **[`color_utils.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/color_utils.py)**: Lightening, darkening, and conversion functions for styling.
  - **[`draggable_list.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/draggable_list.py)**: Grid container that enables reordering list items.
  - **[`factory.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/factory.py)**: Component generator implementing consistent typography and padding design tokens.
  - **[`friend_list.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/friend_list.py)**: UI widget mapping active League client friends with one-click invite options.
  - **[`hotkey_recorder.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/hotkey_recorder.py)**: Captures global keyboard shortcuts to bind to UI functions.
  - **[`hover.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/hover.py)**: Handles hover interactions, scaling, and brightness animation triggers.
  - **[`lol_toggle.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/lol_toggle.py)**: Styled CustomTkinter switches matching the League Client theme.
  - **[`mini_player.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/mini_player.py)**: Drag-and-drop floating widget for minimal system overhead during active matches.
  - **[`priority_grid.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/priority_grid.py)**: Champion prioritization editor for drafting.
  - **[`session_header.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/session_header.py)**: Title bar displaying LCU connection status and active profile info.
  - **[`settings_panel.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/settings_panel.py)**: Configurations dashboard containing general, hotkey, and advanced settings.
  - **[`settings_row.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/settings_row.py)**: Standardized rows for setting controls.
  - **[`tab_bar.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/tab_bar.py)**: Custom segmented navigation controls.
  - **[`toast.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/toast.py)**: Toast notification system for non-blocking status alerts.
  - **[`toggle_row.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/toggle_row.py)**: Specialized settings row featuring a LoLToggle switch.
  - **[`tooltip.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/tooltip.py)**: Floating help text boxes for interface explanation.
  - **[`tray_icon.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/ui/components/tray_icon.py)**: Native system tray support allowing minimization to background.

## 📁 `src/utils/`
Stateless utility functions supporting core loops.
- **[`acrylic_blur.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/utils/acrylic_blur.py)**: Applies a frosted glass (acrylic) background effect using Windows DWM APIs.
- **[`focus_states.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/utils/focus_states.py)**: Configures gold keyboard focus indicators for accessibility and navigation.
- **[`logger.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/utils/logger.py)**: Handles file writing for `debug.log`/`error.log` and maintains in-memory history logs.
- **[`path_utils.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/utils/path_utils.py)**: Resolves paths dynamically when running from source or within a PyInstaller bundle.
- **[`smooth_scroll.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/src/utils/smooth_scroll.py)**: Enhances `CTkScrollableFrame` with momentum-based inertial easing.

## 📁 Root Directories & Scripts
- **[`build.bat`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/build.bat)**: Runs PyInstaller with `LeagueLoop.spec` to build `dist/LeagueLoop.exe`.
- **[`installer.iss`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/installer.iss)**: Inno Setup compiler script to bundle the executable into a setup package.
- **[`launch_dev.bat`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/launch_dev.bat)**: Configures the python execution environment and starts development.
- **[`run.py`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/run.py)**: Shared entry point setting up paths and calling main.
- **📁 [`tests/`](file:///c:/Users/Administrator/antigravity-worspaces-1/LeagueLoop/tests)**: Pytest unit test suite targeting components, services, and utils.
