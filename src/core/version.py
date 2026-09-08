"""
LeagueLoop Version
==================
Version format:  {major}-{month}-{day_of_year}-{HHMM}

This file is updated every time source code changes.
The version reflects the date/time of the last code modification.
It is NOT auto-generated at build or runtime.

Formula:
  {major}       = major version constant — 2 since automation, account
                  switching, champion data and the state pipeline were rebuilt.
                  (The PySide6 shell that briefly shared this line has been
                  removed; the CustomTkinter shell is the application again.)
  {month}       = 2-digit month (01-12)
  {day_of_year} = days that have passed this year (1-366, Julian day)
  {HHMM}        = hour and minute of the change (24hr)

Bump this with every change. `tools/bump_version.py` writes it for you rather
than leaving it to be remembered.
"""

__version__ = "2-09-251-0706"
