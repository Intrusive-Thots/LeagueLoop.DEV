<div align="center">
  <img src="assets/app.png" alt="LeagueLoop Icon" width="128"/>
  <h1>LeagueLoop.DEV</h1>
  <p><strong>Advanced Automation, PySide6 Frameless Elegance, and Ultimate Matchmaking Control for League of Legends</strong></p>
</div>

---

## ⚡ Overview

**LeagueLoop** is an autonomous, high-performance League of Legends companion client written in Python and **PySide6**. Operating alongside the Riot Client and League Client Update (LCU) API, LeagueLoop bypasses repetitive UI workflows to get you into the game effortlessly.

Whether you're dodging toxic lobbies, insta-locking ARAM priorities, switching Riot accounts with one click, or managing automated matchmaking, LeagueLoop provides a Riot-inspired frameless desktop interface with vector icons and real-time LCU WebSocket feedback.

---

## 🔥 Key Features

### 1. **Complete Automation Engine**
- **Auto-Accept Ready Check**: Automatically accepts match pop-ups with configurable delay.
- **Priority Sniper & Auto-Pick**: Insta-lock priority champions, role overrides, and automated rune imports.
- **Multi-Account Manager (`AccountsPage`)**: Manage saved Riot accounts with encrypted credential storage and one-click account switching.
- **Client Launcher & Auto-Launcher**: Manual `🚀 LAUNCH LEAGUE CLIENT` button and auto-launcher engine loop (`auto_launch_client`) when LCU is disconnected.
- **Draft Assistant & Role Enforcer**: Dynamic role hovering, teammate respect algorithms, and arena synergy picks.
- **Chat Warden**: Monitors lobby chat for toxic keywords or requests.
- **Auto-Honor System**: Post-game statistics skipping and automatic teammate honoring.

### 2. **Modern PySide6 Desktop Shell**
- **Frameless Hextech Windows**: Win32 window snapping and docking directly alongside the League Client.
- **Vector Icons & Design Tokens**: High-DPI `VectorIconPainter` and high-contrast color design tokens (`#F8F6F0`, `#F0C674`, `#A8B8CC`).
- **Robust Error Logging**: Global exception hooks (`sys.excepthook`, `threading.excepthook`, `faulthandler`), rotating `debug.log`/`error.log`, and an in-app `📁 OPEN LOGS FOLDER` button.
- **Remote Link REST API**: Built-in HTTP REST API on port 8337 for mobile app and remote control integration.

---

## 📚 Documentation & Guides

Comprehensive documentation is available in the `docs/` directory:

- 🏗️ **[Architecture Guide](docs/architecture.md)** — Core engine loops, PySide6 UI shell, service layer, and EventBus mappings.
- 🛠️ **[Development Guide](docs/development.md)** — Setup instructions, virtual environment configuration, and running unit tests.
- 🔧 **[Troubleshooting & Diagnostics](docs/troubleshooting.md)** — Client detection, LCU self-healing, log directories, and error resolution.
- 🗺️ **[Feature Roadmap](docs/roadmap.md)** — Sprint roadmap, completed milestones, and upcoming features.
- 📋 **[Comprehensive Improvement Plan](docs/improvement_plan.md)** — Master 16-phase architectural refactoring & modernization plan.

---

## 🛠 Quick Start for Developers

```powershell
# Clone Repository
git clone https://github.com/Intrusive-Thots/LeagueLoop.DEV.git
cd LeagueLoop.DEV

# Activate Virtual Environment & Install Dependencies
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run Development App
.\launch_dev.bat

# Run Automated Test Suite (26 test files)
$env:PYTHONPATH="src"
python -m pytest tests/
```

---

## ⚙ Legal & Disclaimer
_LeagueLoop was created under Riot Games' policy using assets owned by Riot Games. Riot Games does not endorse or sponsor this project. The creator is **NOT** liable for any account suspensions, system issues, or penalties incurred while using this software. Using LCU Automation is done entirely at your own risk._
