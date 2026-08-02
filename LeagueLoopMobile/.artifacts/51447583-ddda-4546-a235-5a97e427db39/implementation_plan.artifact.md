# Task 2: ReadyCheck Integration Implementation Plan

This plan outlines the steps to integrate the ReadyCheck functionality, including real-time socket communication and a Glassmorphism UI overlay.

## Proposed Changes

### Data Layer

#### [NEW] [SocketClient.kt](file:///C:/Users/Malcolm/LeagueLoop.DEV/LeagueLoopMobile/app/src/main/java/com/example/myapplication/data/network/SocketClient.kt)
- Create a `SocketClient` class using OkHttp's WebSocket implementation.
- Implement methods to connect to the desktop client.
- Handle "Match Found" messages from the server.
- Implement methods to send "Accept" and "Decline" actions.

### UI Layer

#### [NEW] [ReadyCheckViewModel.kt](file:///C:/Users/Malcolm/LeagueLoop.DEV/LeagueLoopMobile/app/src/main/java/com/example/myapplication/ui/readycheck/ReadyCheckViewModel.kt)
- Manage the connection state and Ready Check event state.
- Expose flows for the UI to observe.

#### [NEW] [ReadyCheckOverlay.kt](file:///C:/Users/Malcolm/LeagueLoop.DEV/LeagueLoopMobile/app/src/main/java/com/example/myapplication/ui/readycheck/ReadyCheckOverlay.kt)
- Implement a Compose-based overlay with a Glassmorphism theme.
- Display "Accept" and "Decline" buttons.
- Show a countdown or timer if provided by the server.

### Integration

#### [MODIFY] [MainActivity.kt](file:///C:/Users/Malcolm/LeagueLoop.DEV/LeagueLoopMobile/app/src/main/java/com/example/myapplication/MainActivity.kt)
- Initialize the `ReadyCheckViewModel`.
- Display the `ReadyCheckOverlay` when a match is found.

## Verification Plan

### Automated Tests
- Unit tests for `SocketClient` to verify message parsing and action syncing (using a mock server).
- Unit tests for `ReadyCheckViewModel` to verify state transitions.

### Manual Verification
- Run the app and simulate a "Match Found" event from a desktop client (or a mock desktop client).
- Verify the UI overlay appears with the correct styling.
- Verify that clicking "Accept" or "Decline" sends the correct message back to the client.
