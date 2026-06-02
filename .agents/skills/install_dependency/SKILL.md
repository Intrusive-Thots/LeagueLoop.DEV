---
name: Install Dependency
description: Install a new pip dependency into the project venv and update requirements.txt
---

# Install Dependency

## Steps

1. Activate the venv:
```powershell
& "c:\Users\Administrator\antigravity-worspaces-1\antigravity-worspaces\.venv\Scripts\Activate.ps1"
```

2. Install the package:
```powershell
pip install <package_name>
```

3. Freeze and update requirements:
```powershell
pip freeze | Select-String -NotMatch "pywin32|pyinstaller" > requirements.txt
```

## Critical Rules
- **ALWAYS** install into the venv before importing anything new in code.
- Update `requirements.txt` after every new install.
- Filter out dev-only packages (pyinstaller, pywin32) from the freeze output if not needed at runtime.
- Verify the import works: `python -c "import <package_name>"`
