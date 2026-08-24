"""
Removed. The ARAM screen is a mode on the Priority screen.

There were two near-identical screens editing two config keys, and they
drifted: this one's "Paste list" called `self.current_ids()` (the method here
was `_current_ids`) and then `self.list_widget` (here it was
`prio_list_widget`), so the button raised `AttributeError` straight out of
the slot. It also held the only controls that ever wrote `aram_bench_swap`
and `aram_auto_reroll` — while being unreachable from the app, which is why
those two keys were read by the engine and written by nothing.

Both switches now live on the Priority screen, shown when the ARAM mode is
selected. `QtAramTab` is re-exported so any stale import keeps working.

The file is a shim rather than a deletion because the desktop bridge this
was edited through cannot remove files. Delete it whenever you like.
"""
from __future__ import annotations

from ui.qt.widgets.champion_list_tab import QtAramTab

__all__ = ["QtAramTab"]
