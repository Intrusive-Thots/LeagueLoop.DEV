# LeagueLoop.DEV Development Guide

## Prerequisites
- **Python**: 3.11+
- **OS**: Windows 10/11
- **Dependencies**: `PySide6`, `urllib3`, `psutil`, `pywin32`

## Setup Instructions

1. **Activate Virtual Environment**:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install Requirements**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Run Application in Development Mode**:
   ```powershell
   .\launch_dev.bat
   ```
   Or manually:
   ```powershell
   $env:PYTHONPATH="src"
   python run.py
   ```

4. **Run Test Suite**:
   ```powershell
   $env:PYTHONPATH="src"
   python -m pytest tests/
   ```

5. **Build Executable**:
   ```powershell
   .\build.bat
   ```
