# LeagueLoop.DEV Development Guide

## Prerequisites
- **Python**: 3.11+
- **OS**: Windows 10/11
- **Dependencies**: See `requirements.txt` (includes CustomTkinter, PySide6 for future migration, and runtime dependencies)

## Setup Instructions

1. **Clone Repository**:
   ```bash
   git clone https://github.com/Intrusive-Thots/LeagueLoop.DEV.git
   cd LeagueLoop.DEV
   ```

2. **Activate Virtual Environment** (recommended):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install Requirements**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Run Application in Development Mode**:
   ```powershell
   python run.py
   ```
   
   Or cross-platform:
   ```bash
   # Linux/macOS
   PYTHONPATH=src python -m core.main
   
   # Windows PowerShell
   $env:PYTHONPATH="src"
   python -m core.main
   ```

5. **Run Test Suite**:
   ```powershell
   $env:PYTHONPATH="src"
   python -m pytest tests/
   ```

---

## Release Packaging (Manual, Windows Only)

> ⚠️ **Warning**: Build commands are Windows-only and should not be part of routine development/test loops. Only run these when preparing a release.

To build the executable installer:

```powershell
.\build.bat
```

This runs PyInstaller and InnoSetup to create `LeagueLoop_Installer.exe`. Requires:
- InnoSetup installed at standard path
- Windows 10/11 environment
- Valid code signing certificate (optional, for production releases)
