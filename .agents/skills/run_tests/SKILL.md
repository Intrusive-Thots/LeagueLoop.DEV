---
name: Run Tests
description: Run the LeagueLoop test suite and diagnose failures
---

# Run Tests

## Test Location
Tests are in: `tests/`

## Steps

1. Run all tests:
```powershell
$env:PYTHONPATH = "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\src"
& "c:\Users\Administrator\antigravity-worspaces-1\antigravity-worspaces\.venv\Scripts\python.exe" -m pytest tests/ -v
```

2. Run a specific test file:
```powershell
$env:PYTHONPATH = "c:\Users\Administrator\antigravity-worspaces-1\LeagueLoop\src"
& "c:\Users\Administrator\antigravity-worspaces-1\antigravity-worspaces\.venv\Scripts\python.exe" -m pytest tests/test_ui_kwargs.py -v
```

3. Run with output capture disabled (for debugging):
```powershell
& "c:\Users\Administrator\antigravity-worspaces-1\antigravity-worspaces\.venv\Scripts\python.exe" -m pytest tests/ -v -s
```

## Writing New Tests

1. Create `tests/test_<feature>.py`:
```python
import pytest

def test_my_feature():
    assert 1 + 1 == 2
```

2. For tests that import project modules:
```python
import sys
sys.path.insert(0, "c:\\Users\\Administrator\\antigravity-worspaces-1\\LeagueLoop\\src")
from services.automation import AutomationEngine
```

## Notes
- Always set `PYTHONPATH` before running tests.
- UI tests (importing customtkinter) may fail in headless environments.
- Use `test_ui_kwargs.py` as a reference for testing widget instantiation.
