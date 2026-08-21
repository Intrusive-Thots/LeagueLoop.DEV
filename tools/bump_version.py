"""
Stamp `core/version.py` with the current time.

The version is meant to move with every source change, which means it will be
forgotten unless it is one command. Run this before committing:

    python tools/bump_version.py
    python tools/bump_version.py --check    # non-zero if it looks stale
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import sys

MAJOR = 2
ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
VERSION_FILE = os.path.join(ROOT, "src", "core", "version.py")
PATTERN = re.compile(r'^__version__ = "(?P<value>[^"]*)"', re.M)


def current_version() -> str:
    now = datetime.datetime.now()
    days_left = (datetime.date(now.year, 12, 31) - now.date()).days
    return "{}-{:02d}-{:03d}-{:02d}{:02d}".format(
        MAJOR, now.month, days_left, now.hour, now.minute
    )


def read_version() -> str:
    with open(VERSION_FILE, encoding="utf-8") as handle:
        match = PATTERN.search(handle.read())
    return match.group("value") if match else ""


def write_version(value: str) -> None:
    with open(VERSION_FILE, encoding="utf-8") as handle:
        text = handle.read()
    text = PATTERN.sub('__version__ = "{}"'.format(value), text, count=1)
    with open(VERSION_FILE, "w", encoding="utf-8") as handle:
        handle.write(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="Report without writing; exit 1 if the major version is wrong.",
    )
    args = parser.parse_args()

    existing = read_version()
    if args.check:
        major = existing.split("-", 1)[0] if existing else ""
        if major != str(MAJOR):
            print("Version {} is not major {}".format(existing or "(missing)", MAJOR))
            return 1
        print("Version {} looks right.".format(existing))
        return 0

    value = current_version()
    write_version(value)
    print("{} -> {}".format(existing or "(none)", value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
