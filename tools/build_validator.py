"""
build_validator.py — Automated pre-build verification utility for LeagueLoop.
Validates environment, test suite status, version formatting, required assets, and spec file integrity.
"""

import io
import json
import os
import re
import sys
import subprocess
from pathlib import Path

# Force UTF-8 encoding on stdout for Windows compatibility
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def validate_version(project_root: Path) -> str:
    version_file = project_root / "src" / "core" / "version.py"
    if not version_file.exists():
        raise FileNotFoundError(f"Version file missing at {version_file}")
    
    content = version_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError("Could not parse __version__ string from src/core/version.py")
    
    version_str = match.group(1)
    print(f"[OK] Version detected: {version_str}")
    return version_str


def validate_test_suite(project_root: Path) -> bool:
    print("Executing pre-build test validation suite...")
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    python_bin = str(venv_python) if venv_python.exists() else sys.executable

    try:
        res = subprocess.run([python_bin, "-m", "pytest", "-q"], cwd=str(project_root), capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print("[FAIL] Test suite validation timed out after 30s.")
        return False
    if res.returncode != 0:
        print(f"[FAIL] Test suite validation failed:\n{res.stdout}\n{res.stderr}")
        return False
    print("[OK] All tests passed successfully.")
    return True


def validate_files(project_root: Path) -> bool:
    required_paths = [
        project_root / "LeagueLoop.spec",
        project_root / "installer.iss",
        project_root / "src" / "ui" / "theme" / "design_tokens.json",
        project_root / "assets" / "app.ico",
    ]
    missing = [str(p) for p in required_paths if not p.exists()]
    if missing:
        print(f"[FAIL] Missing required build files: {missing}")
        return False
    print("[OK] All required spec files and assets present.")
    return True


def main():
    root = Path(__file__).resolve().parent.parent
    print("=" * 60)
    print("  LeagueLoop Build Pipeline Pre-Flight Verification")
    print("=" * 60)

    try:
        ver = validate_version(root)
        files_ok = validate_files(root)
        tests_ok = validate_test_suite(root)

        if files_ok and tests_ok:
            print("\nBUILD READINESS: READY FOR COMPILATION")
            sys.exit(0)
        else:
            print("\nBUILD READINESS: UNREADY (Validation Failures)")
            sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Pre-flight error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
