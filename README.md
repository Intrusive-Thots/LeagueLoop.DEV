<div align="center">
  <img src="assets/app.png" alt="LeagueLoop" width="120"/>
  <h1>LeagueLoop</h1>
  <p><strong>A League Client companion for queue, champ select, and post-game automation.</strong></p>

  <p>
    <a href="https://github.com/Intrusive-Thots/LeagueLoop.DEV/actions/workflows/ci.yml"><img src="https://github.com/Intrusive-Thots/LeagueLoop.DEV/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
    <img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue" alt="Python 3.10-3.13"/>
    <img src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-lightgrey" alt="Windows"/>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"/></a>
  </p>
</div>

---

## What it is

LeagueLoop is a Python desktop app that sits beside the League Client and handles
the repetitive parts of getting into a game: accepting queue pops, hovering and
locking your priority champion, banning, honoring afterwards, and switching
accounts between sessions.

It talks to the League Client over the client's own local REST and WebSocket
API (the LCU) — the same interface the client's own UI uses. It reads the
lockfile Riot writes at startup for the port and password, subscribes to
gameflow events, and reacts to phase changes.

## Scope — what it does and does not touch

This is the project's one hard architectural rule, and it is worth stating up
front because it determines which features can ever exist here.

| Used | Never used |
|---|---|
| LCU REST API — `https://127.0.0.1:{port}` | Live Client Data API — port 2999 |
| LCU WebSocket events — `wss://` | Game memory, process handles, injection |
| Riot Client API, lockfile auth | Overlays drawn over the running game |
| Lobby, ReadyCheck, ChampSelect, EndOfGame | Any data read while a match is live |

Nothing in LeagueLoop reads or writes the running game process. Everything it
does happens in the client, between games. Full statement of the constraint:
[`.agents/ARCHITECTURE_CONSTRAINTS.md`](.agents/ARCHITECTURE_CONSTRAINTS.md).

## Screenshots

<div align="center">
  <table>
    <tr>
      <td align="center"><img src="assets/screenshots/lobby_idle.png" alt="Lobby" width="240"/><br/><sub>Lobby — idle</sub></td>
      <td align="center"><img src="assets/screenshots/connected.png" alt="Connected" width="240"/><br/><sub>Connected</sub></td>
    </tr>
    <tr>
      <td align="center"><img src="assets/screenshots/champ_select.png" alt="Champ select" width="240"/><br/><sub>Champ select</sub></td>
      <td align="center"><img src="assets/screenshots/mode_picker.png" alt="Queue picker" width="240"/><br/><sub>Queue picker</sub></td>
    </tr>
  </table>
</div>

## Features

### Queue and lobby

- **Auto-accept** ready checks, with a configurable delay
- **Queue picker** that reads the client's live lobby types rather than a
  hardcoded list, so new and rotating modes appear on their own
- **Auto-requeue** after a dodge or a returned lobby
- **Auto-join** a friend's lobby, restricted to a list of players you name

### Champ select

- **Priority picker** — an ordered champion list, with per-role overrides
  (`priority_MIDDLE`, `priority_TOP`, …) falling back to the global list
- **Auto-hover and auto-lock**, with a backup cascade when a pick is taken
- **Auto-ban** from an ordered ban list, optionally skipping a champion a
  teammate is already hovering
- **Draft assistant** — role detection and a deterministic priority engine that
  scores candidates against your lists and the current availability
- **ARAM** — its own priority list, bench swapping to a higher-priority
  champion, and auto-reroll
- **Arena** — synergy pair picking from a configured pairs list
- **Auto-dodge** on a blacklist of players (gated behind its own switch — it
  force-closes the client)
- **Chat warden** — watches lobby chat for abuse and warns. Off by default,
  since it reads every message in the lobby
- **Auto random skin** on lock-in
- **Compact "orb" mode** that pins beside the client and stays out of the way

### Post-game

- **Auto-honor**, targeting friends or top performers, rate-limit aware
- **Skip stats** — clicks through the post-game screens back to the lobby

### Accounts and utilities

- **Account manager** with passwords encrypted at rest using Windows DPAPI
  (`CryptProtectData`), tied to your Windows user — the store is useless if
  copied to another machine
- **Auto-login** and account switching, with per-account wallet tracking
- **Friend list** with mass invite and custom status injection
- **Loot tools** — key crafting from fragments, planned chest opens, mission
  and milestone reward claims
- **Global hotkeys** for launching the client, toggling automation, and
  entering compact mode
- **Window attachment** — the companion follows the client, hides when it
  minimises, and returns when it restores

### Mobile companion

A local HTTP API on port `8337` exposes status, champ select actions, queue
control, and account switching to the Android companion in
[`LeagueLoopMobile/`](LeagueLoopMobile/). It binds to the local network and
adds its own Windows Firewall rule on first run.

Endpoints include `/status`, `/champ-select`, `/champ-select/{pick,ban,lock,reroll,bench-swap}`,
`/ready-check/{accept,decline}`, `/queue-modes`, `/accounts`, `/config`, `/health`.

## Requirements

- Windows 10 or 11 — the app uses DPAPI, pywin32 and Win32 window APIs
  throughout and does not run on macOS or Linux
- Riot Client and League of Legends installed
- Python 3.10–3.13, to run from source

## Install

### Installer (recommended)

Download and run the latest `LeagueLoop_Installer.exe` from
[Intrusive-Thots/LeagueLoop-Installer](https://github.com/Intrusive-Thots/LeagueLoop-Installer).

### From source

```bash
git clone https://github.com/Intrusive-Thots/LeagueLoop.DEV.git
cd LeagueLoop.DEV

python -m venv .venv
.venv\Scripts\activate

pip install -r config/requirements.txt
python run.py
```

`config/requirements.txt` is the pinned, complete dependency set and is what CI
installs. The `requirements.txt` at the repo root is an unpinned subset kept for
older tooling.

Start the League Client first, or use the launch hotkey once LeagueLoop is
running — it finds the client through the lockfile and will wait for one to
appear.

## Configuration

`config.json` and `accounts.json` are written at runtime, and where they land
depends on how the app was started:

| Started as | Config and accounts | Logs |
|---|---|---|
| Installed executable | `%LOCALAPPDATA%\LeagueLoop\` | `%LOCALAPPDATA%\LeagueLoop\logs\` |
| `python run.py` from source | the working directory — the repo root | `%LOCALAPPDATA%\LeagueLoop\logs\` |

Two examples in `config/` show the expected shape:

- [`config/config.json.example`](config/config.json.example) — automation
  toggles, delays, hotkeys, priority picker
- [`config/accounts.json.example`](config/accounts.json.example) — account
  store layout. `password_enc` is DPAPI ciphertext; it is never written in
  plaintext and cannot be filled in by hand

Copy one next to `run.py` without the `.example` suffix to start from it. Most
settings are reachable from the Settings and Automations tabs, so hand-editing
is rarely needed.

Every configuration key is declared once in
[`src/core/config_keys.py`](src/core/config_keys.py). Both the UI and the
automation engine import from there — a key written by a screen but read by
nothing is a test failure, not a silent no-op.

## Development

### Layout

```
src/core/        App shell, event bus, state, config keys, version
src/services/    LCU client, automation engine, accounts, draft, loot, local API
src/ui/          CustomTkinter shell — sidebar, tabs, components, theme
tests/           Test suite (pytest)
tools/           Version bump, icon build, scaling and overflow checks
build_scripts/   PyInstaller spec, Inno Setup script, dev launchers
docs/            Architecture, development, troubleshooting, roadmap
.agents/         Architecture constraints, repo history, agent skills
```

### Tests

```bash
pytest
```

`pytest.ini` sets `pythonpath = src` and `testpaths = tests`, so plain `pytest`
from the repo root is enough. Some UI tests additionally need
`config/requirements-qt.txt` installed; without it those modules fail to
import while the rest of the suite runs normally.

CI runs an import smoke test across Python 3.10–3.13 on `windows-latest`,
then the full suite on 3.11.

### Build

```bash
pyinstaller build_scripts/LeagueLoop.spec --clean -y
ISCC.exe build_scripts/installer.iss    # requires Inno Setup
```

Tagging a commit `v*` runs the release workflow in
[`.github/workflows/build-installer.yml`](.github/workflows/build-installer.yml),
which builds the executable and publishes the installer.

### Versioning

`src/core/version.py` holds a `{major}-{month}-{day_of_year}-{HHMM}`
string that is bumped on every change. Use `python tools/bump_version.py`
rather than editing it by hand.

## Docs

| | |
|---|---|
| [Architecture](docs/architecture.md) | Layers, event flow, service boundaries |
| [Development](docs/development.md) | Local setup and workflow |
| [Troubleshooting](docs/troubleshooting.md) | Common failures and log locations |
| [Roadmap](docs/roadmap.md) | Planned work |
| [Changelog](docs/CHANGELOG.md) | Release history |
| [ADR 0001](docs/adr/0001-lcu-websocket-primary.md) | Why the WebSocket is primary over polling |

## Legal

LeagueLoop is an unofficial community project. It is not endorsed by, affiliated
with, or sponsored by Riot Games, and Riot Games is not responsible for it.
League of Legends and all associated assets are property of Riot Games, Inc.,
used here under Riot's [Legal Jibber Jabber](https://www.riotgames.com/en/legal)
policy for non-commercial projects.

Automating the League Client carries risk. Riot's Terms of Service restrict
third-party tools, and account action is possible. You use this software at your
own risk; the authors accept no liability for bans, restrictions, or any other
penalty applied to your account.

## License

[MIT](LICENSE) © Intrusive-Thots
