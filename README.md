<div align="center">
  <img src="assets/app.png" alt="LeagueLoop Icon" width="128"/>
  <h1>LeagueLoop</h1>
  <p><strong>LCU companion for automation, draft tools, and matchmaking control</strong></p>
</div>

---

## Overview

**LeagueLoop** is a Python companion for the League Client (LCU). It automates pre-game, champ select, and post-game workflows via the official LCU REST and WebSocket APIs. It does **not** interact with the running game process or Live Client Data API.

UI is currently **CustomTkinter**; a **PySide6** migration is planned (see `docs/improvement_plan.md`).

## Scope (hard constraint)

| Allowed | Forbidden |
|---------|-----------|
| LCU REST / WebSocket | Live Client Data (port 2999) |
| Riot Client lockfile / auth | Game memory / process injection |
| Lobby, ChampSelect, EndOfGame | In-game overlays or live stats |

Details: [`.agents/ARCHITECTURE_CONSTRAINTS.md`](.agents/ARCHITECTURE_CONSTRAINTS.md)

## Screenshots

<div align="center">
  <table>
    <tr>
      <td align="center"><img src="assets/screenshots/lobby_idle.png" alt="Lobby — Idle" width="220"/><br/><sub>Lobby — Idle</sub></td>
      <td align="center"><img src="assets/screenshots/connected.png" alt="Connected" width="220"/><br/><sub>Connected & Ready</sub></td>
    </tr>
    <tr>
      <td align="center"><img src="assets/screenshots/champ_select.png" alt="Champ Select" width="220"/><br/><sub>Champ Select</sub></td>
      <td align="center"><img src="assets/screenshots/mode_picker.png" alt="Mode Picker" width="220"/><br/><sub>Queue Mode Selector</sub></td>
    </tr>
  </table>
</div>

---

## Features

- **Auto-Accept** and queue control
- **Priority Sniper / Auto-Pick** with backups and bans
- **Draft Assistant** (role enforcer + teammate respect)
- **Arena Synergy Picker** and **ARAM** priority lists
- **Auto-Honor** (friends / top performers, rate-limit aware)
- **Account manager**, friend list, status injection
- **Compact "Orb" mode** for draft
- Event-driven LCU WebSocket backend (non-blocking)

## Prerequisites

- Windows 10/11
- Riot Client + League of Legends
- Python 3.10+ (source runs)

## Install & run

**Installer** (recommended):

1. Download [LeagueLoop_Installer.exe](https://github.com/Intrusive-Thots/LeagueLoop-Installer)
2. Install and launch

**From source:**

```bash
git clone https://github.com/Intrusive-Thots/LeagueLoop.DEV.git
cd LeagueLoop.DEV
pip install -r requirements.txt
python run.py
```

**Build executable:**

```bash
pyinstaller LeagueLoop.spec --clean -y
ISCC.exe installer.iss   # if Inno Setup installed
```

## Docs

- [Architecture](docs/architecture.md)
- [Development](docs/development.md)
- [Improvement plan](docs/improvement_plan.md)
- [Troubleshooting](docs/troubleshooting.md)

## Legal

LeagueLoop uses Riot-owned assets under Riot’s policies. Riot does not endorse this project. Use of LCU automation is at your own risk; the author is not liable for bans or other penalties.
