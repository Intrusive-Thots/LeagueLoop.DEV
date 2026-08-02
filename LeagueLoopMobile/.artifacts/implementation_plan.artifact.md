# Implementation Plan - Drafting Dashboard

Implement the Champion Select, Rune Management, and Settings Dashboard screens using Jetpack Compose and Navigation 3, maintaining a Premium Glassmorphism theme.

## User Review Required

> [!IMPORTANT]
> - **Navigation 3 Migration**: I will refactor `MainActivity` to use `androidx.navigation3` for state-driven navigation.
> - **Socket Models**: I will extend `SocketMessage` to handle detailed drafting states. I'm assuming a schema for `DRAFT_UPDATE` and `RUNE_UPDATE` messages.
> - **Adaptive Layout**: The drafting screen will use `ListDetailPaneScaffold` to adapt to larger screens, showing picks/bans on one side and champion search/runes on the other.

## Open Questions

- What is the exact JSON structure for the drafting state from the server? (I will assume a reasonable structure based on typical MOBA drafts).
- Should the "Settings Dashboard" be a separate screen or a bottom sheet/overlay? (Plan: Separate screen accessible via navigation).

## Proposed Changes

### [Navigation & Foundation]

#### [MODIFY] [MainActivity.kt](file:///C:/Users/Malcolm/LeagueLoop.DEV/LeagueLoopMobile/app/src/main/java/com/example/myapplication/MainActivity.kt)
- Refactor to use `NavDisplay` and `NavBackStack`.
- Handle screen transitions between `Discovery`, `ChampionSelect`, and `Settings`.

#### [MODIFY] [SocketMessages.kt](file:///C:/Users/Malcolm/LeagueLoop.DEV/LeagueLoopMobile/app/src/main/java/com/example/myapplication/data/network/SocketMessages.kt)
- Add data classes for `DraftState`, `Champion`, `RunePage`, etc.
- Add new message types and action constants.

### [Champion Select Feature]

#### [NEW] [ChampionSelectScreen.kt](file:///C:/Users/Malcolm/LeagueLoop.DEV/LeagueLoopMobile/app/src/main/java/com/example/myapplication/ui/draft/ChampionSelectScreen.kt)
- Implement the real-time drafting UI.
- Show bans, team picks, and enemy picks.
- Integrated champion search and selection.

#### [NEW] [DraftViewModel.kt](file:///C:/Users/Malcolm/LeagueLoop.DEV/LeagueLoopMobile/app/src/main/java/com/example/myapplication/ui/draft/DraftViewModel.kt)
- Manage drafting state from WebSocket messages.
- Handle pick/ban actions.

### [Rune Management Feature]

#### [NEW] [RuneManagementSection.kt](file:///C:/Users/Malcolm/LeagueLoop.DEV/LeagueLoopMobile/app/src/main/java/com/example/myapplication/ui/runes/RuneManagementSection.kt)
- UI for viewing and adjusting rune pages.
- Glassmorphism styling for rune nodes.

### [Settings & Auto-Draft Feature]

#### [NEW] [SettingsDashboard.kt](file:///C:/Users/Malcolm/LeagueLoop.DEV/LeagueLoopMobile/app/src/main/java/com/example/myapplication/ui/settings/SettingsDashboard.kt)
- Toggle preferences like "Auto-Ban Blitzcrank".
- Save preferences locally or sync with server.

## Verification Plan

### Automated Tests
- `DraftViewModelTest`: Verify state updates correctly when receiving `DRAFT_UPDATE` messages.
- `SocketClientTest`: Ensure actions are sent with correct JSON format.

### Manual Verification
- Verify Glassmorphism effects (blur, transparency) match the design intent.
- Ensure Edge-to-Edge is respected across all new screens.
- Test adaptive layout on different screen sizes (Phone/Tablet).
