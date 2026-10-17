"""
Stamp `core/version.py` and `installer.iss` with the current time.

The version is meant to move with every source change, which means it will be
forgotten unless it is one command. Run this before committing:

    python tools/bump_version.py
    python tools/bump_version.py --check    # non-zero if out of sync or stale
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
from typing import Tuple, Optional

MAJOR = 2
ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
VERSION_FILE = os.path.join(ROOT, "src", "core", "version.py")
INSTALLER_ISS = os.path.join(ROOT, "installer.iss")

PATTERN = re.compile(r'^__version__ = "(?P<value>[^"]*)"', re.M)
ISS_APP_VERSION_PATTERN = re.compile(r'^#define AppVersion "(?P<value>[^"]*)"', re.M)
ISS_VERSION_INFO_PATTERN = re.compile(r'^#define VersionInfoVersion "(?P<value>[^"]*)"', re.M)


def current_version() -> str:
    now = datetime.datetime.now()
    day_of_year = now.timetuple().tm_yday
    return "{}-{:02d}-{:03d}-{:02d}{:02d}".format(
        MAJOR, now.month, day_of_year, now.hour, now.minute
    )


def to_version_info(value: str) -> str:
    """Converts hyphen-separated version string to dot-separated VersionInfoVersion for Inno Setup."""
    return value.replace("-", ".")


def read_version(file_path: Optional[str] = None) -> str:
    path = file_path or VERSION_FILE
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as handle:
        match = PATTERN.search(handle.read())
    return match.group("value") if match else ""


def write_version(value: str, file_path: Optional[str] = None) -> None:
    path = file_path or VERSION_FILE
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    text = PATTERN.sub('__version__ = "{}"'.format(value), text, count=1)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def read_installer_versions(file_path: Optional[str] = None) -> Tuple[str, str]:
    path = file_path or INSTALLER_ISS
    if not os.path.exists(path):
        return "", ""
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    m_app = ISS_APP_VERSION_PATTERN.search(content)
    m_info = ISS_VERSION_INFO_PATTERN.search(content)
    app_ver = m_app.group("value") if m_app else ""
    info_ver = m_info.group("value") if m_info else ""
    return app_ver, info_ver


def write_installer_versions(value: str, file_path: Optional[str] = None) -> None:
    path = file_path or INSTALLER_ISS
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    content = ISS_APP_VERSION_PATTERN.sub(f'#define AppVersion "{value}"', content, count=1)
    content = ISS_VERSION_INFO_PATTERN.sub(f'#define VersionInfoVersion "{to_version_info(value)}"', content, count=1)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def check_version_alignment(
    version_file: Optional[str] = None,
    installer_file: Optional[str] = None
) -> Tuple[bool, str]:
    """Validates that version.py and installer.iss are completely aligned with valid major version."""
    v_path = version_file or VERSION_FILE
    iss_path = installer_file or INSTALLER_ISS

    existing = read_version(v_path)
    if not existing:
        return False, f"Missing or unparseable __version__ in {v_path}"

    major = existing.split("-", 1)[0]
    if major != str(MAJOR):
        return False, f"Version {existing} does not match expected major {MAJOR}"

    if os.path.exists(iss_path):
        app_ver, info_ver = read_installer_versions(iss_path)
        if app_ver != existing:
            return False, f"installer.iss AppVersion ('{app_ver}') does not match version.py ('{existing}')"
        expected_info = to_version_info(existing)
        if info_ver != expected_info:
            return False, f"installer.iss VersionInfoVersion ('{info_ver}') does not match expected ('{expected_info}')"

    return True, f"Version {existing} aligned across version.py and installer.iss"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="Report without writing; exit 1 if versions are misaligned or major version is wrong.",
    )
    parser.add_argument(
        "--no-iss", action="store_true",
        help="Skip updating installer.iss when writing new version.",
    )
    args = parser.parse_args(argv)

    if args.check:
        ok, msg = check_version_alignment()
        if not ok:
            print(f"[FAIL] {msg}")
            return 1
        print(f"[OK] {msg}")
        return 0

    existing = read_version()
    value = current_version()
    write_version(value)
    if not args.no_iss:
        write_installer_versions(value)
    print("{} -> {} (aligned with installer.iss)".format(existing or "(none)", value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
