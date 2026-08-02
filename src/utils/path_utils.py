import os
import sys

def get_asset_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_data_dir():
    """
    Get the directory for saving persistent data (config, logs).
    When running as a PyInstaller executable, use AppData/Local/LeagueLoop.
    Otherwise, use the local directory.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        return os.path.join(appdata, 'LeagueLoop')
    else:
        # Running as script
        return os.path.abspath(".")
