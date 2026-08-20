"""
Priority screen.

The implementation now lives in `champion_list_tab`, shared with ARAM and the
ban list — the three are the same interaction over a different config key.
This module is kept so existing imports of `QtPriorityTab` keep working.
"""
from ui.qt.widgets.champion_list_tab import QtChampionListTab, QtPriorityTab

__all__ = ["QtPriorityTab", "QtChampionListTab"]
