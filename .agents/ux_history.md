# UX / UI Design History

## Design Principles
LeagueLoop.DEV follows modern Riot Games client visual design aesthetics:
1. **Color Palette**: Dark blue-grey backgrounds (`#080E18`, `#0A1424`), hex gold accents (`#C8AA6E`), and icy light text (`#F0E6D2`).
2. **Typography**: Clean hierarchy utilizing Inter sans-serif fonts with distinct weight differentiation for headers, badges, and body text.
3. **Spacing System**: Strict 4px grid spacing (4px, 8px, 12px, 16px, 24px, 32px).
4. **Visual Hierarchy & Feedback**: Micro-animations, subtle glassmorphic borders (`#142236`), smooth hover transitions, and instant visual state feedback on button clicks and hotkey invocations.

## UI Evolution Timeline
- **V1 (CustomTkinter)**: Initial implementation with dark mode CTk components, sidebar navigation, and overlay panels.
- **V2 (PySide6 Qt Shell Migration)**:
  - Header bar: Added custom window drag bar with app status indicators, hotkey badge (`F3 Queue`), active profile status, and window window controls.
  - Sidebar: Vector navigation buttons using `RiotIconWidget` with smooth active state indicator lines.
  - Page stacked layouts: Refactored page rendering under `src/ui/qt/pages/` to allow instant tab switching without widget destruction.
  - Docked / Undocked mode: Support for toggling between docked sidebar panel mode and full desktop app window mode.
