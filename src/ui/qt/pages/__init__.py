"""
PySide6 Pages Package

Pages are imported lazily to avoid import-time dependency chains.
Use direct imports (e.g. from ui.qt.pages.settings_page import SettingsPage)
instead of importing from this package.
"""
# Lazy attribute access — only import a page class when explicitly requested
# from the package namespace.
_PAGE_MAP = {
    "SettingsPage":       "ui.qt.pages.settings_page",
    "FriendsPage":        "ui.qt.pages.friends_page",
    "ChampionsPage":      "ui.qt.pages.champions_page",
    "DashboardPage":      "ui.qt.pages.dashboard_page",
    "PlayPage":           "ui.qt.pages.play_page",
    "CoachPage":          "ui.qt.pages.coach_page",
    "MatchPredictorPage": "ui.qt.pages.match_predictor_page",
    "PatchNotesPage":     "ui.qt.pages.patch_notes_page",
}

__all__ = list(_PAGE_MAP.keys())


def __getattr__(name):
    if name in _PAGE_MAP:
        import importlib
        module = importlib.import_module(_PAGE_MAP[name])
        cls = getattr(module, name)
        globals()[name] = cls  # cache for subsequent access
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
