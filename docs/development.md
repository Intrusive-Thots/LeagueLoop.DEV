# Development Guide

## Prerequisites

- Windows 10/11 (primary target)
- Python 3.10+
- Riot Client + League of Legends

## Setup

```bash
git clone https://github.com/Intrusive-Thots/LeagueLoop.DEV.git
cd LeagueLoop.DEV
pip install -r requirements.txt
```

PySide6 packages are commented out in `requirements.txt` until the UI migration begins. Uncomment them when starting Phase 1 of the improvement plan.

## Run

```bash
python run.py
```

## Tests

```bash
set PYTHONPATH=src
python -m pytest tests/ -v
```

## Build (Windows only)

```bash
pyinstaller LeagueLoop.spec --clean -y
ISCC.exe installer.iss   # requires Inno Setup
```

## Notes

- Core UI is CustomTkinter. PySide6 migration is planned (see `docs/improvement_plan.md`).
- Local API defaults to `127.0.0.1:8337` for security.
