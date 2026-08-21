"""
LeagueLoop Version
==================
Version format:  {major}-{month}-{days_left_in_year}-{HHMM}

This file is updated every time source code changes.
The version reflects the date/time of the last code modification.
It is NOT auto-generated at build or runtime.

Formula:
  {major}     = major version constant — 2 since the Qt shell became the
                application: automation, account switching, champion data and
                the state pipeline were all rebuilt, and the CustomTkinter
                shell is no longer the only one that works.
  {month}     = 2-digit month (01-12)
  {days_left} = days remaining in the year (0-365)
  {HHMM}      = hour and minute of the change (24hr)

Bump this with every change. `tools/bump_version.py` writes it for you rather
than leaving it to be remembered.
"""

__version__ = "2-08-132-1935"
