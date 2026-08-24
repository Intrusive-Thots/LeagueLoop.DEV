import os
import sys

#: The repository root: two levels up from `src/utils/path_utils.py`.
#: Computed from this file's own location, which is the only anchor that does
#: not move.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))


def get_asset_path(relative_path):
    """Absolute path to a bundled resource. Works frozen and from source.

    Resolved against the **project root**, not the working directory. It used
    to be `os.path.abspath(".")`, which is only correct when the app happens
    to be launched from the repository root — a shortcut with a different
    "Start in" folder, or a scheduled task, resolved every icon, every
    champion portrait and every cached asset to a path that did not exist.
    Nothing crashed; the images just silently never appeared.
    """
    base_path = getattr(sys, "_MEIPASS", None)  # PyInstaller's temp folder
    if not base_path:
        base_path = _PROJECT_ROOT
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
