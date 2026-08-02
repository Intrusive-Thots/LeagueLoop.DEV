# LeagueLoop.DEV Product & Technical Roadmap

## Vision
LeagueLoop is the premier autonomous companion overlay for League of Legends, delivering zero-blocking LCU automation, real-time draft intelligence, and sleek CustomTkinter / native Win32 overlay visuals.

## Roadmap Milestones

### Milestone 1: Stability & Test Automation (COMPLETE)
- Comprehensive unit and integration testing across `src/core/`, `src/services/`, and `src/ui/`.
- Headless CI execution without GUI display server or Tkinter Tcl dependencies.
- Automated release validation (`tools/build_validator.py`).

### Milestone 2: Automation & LCU Integration (COMPLETE)
- Instantaneous Auto-Accept and Priority Sniper with custom ban rules.
- Draft Assistant with teammate hover dodge and respect algorithm.
- Arena Synergy Picker V5 with dual/fallback priority arrays.
- Auto-Honor system with algorithmic teammate evaluation and rate limit retry resilience.

### Milestone 3: Advanced Overlay & UX Enhancements (ONGOING)
- Win32 topmost window docking above Riot and League Client windows.
- Draggable compact "Orb" mode for low-profile drafting.
- Dynamic toast alerts and responsive layout resizing.

### Milestone 4: Future Capability Expansion (PLANNED)
- Expanded in-client telemetry and post-game analytical summaries.
- Enhanced multi-account fast switching via encrypted credential store.
- Custom theme pack support and community ARAM priority sharing.
