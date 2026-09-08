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

#: Files that are user data, not source. Each one used to be written to the
#: working directory when running from source and to AppData when frozen, so
#: a dev run and an installed run kept two different sets and neither knew
#: about the other.
DATA_FILES = ("config.json", "accounts.json", "leagueloop.db")
DATA_DIRS = ("sessions",)


def get_data_dir():
    """Where persistent user data lives. Always AppData on Windows.

    This used to return `os.path.abspath(".")` when running from source and
    AppData only when frozen. Two consequences, both bad:

    * **Two sets of data.** A dev run wrote `accounts.json` and `config.json`
      into the repository while the installed build used AppData, and neither
      saw the other's accounts or settings.
    * **Credentials in the working tree.** `accounts.json` sat beside the
      source, and `.gitignore` did not exclude it. It happened not to be
      committed — but a single `git add -A` would have pushed the account
      store to GitHub. That is not a risk worth keeping for a convenience
      nobody asked for.

    Logs already went to AppData unconditionally, so this also makes the data
    and the logs agree about where the application keeps things.
    """
    appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not appdata:
        # Non-Windows (tests, CI) — mirror the same shape under the home
        # directory rather than falling back to the working directory, which
        # is what caused the split in the first place.
        appdata = os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(appdata, "LeagueLoop")
    os.makedirs(path, exist_ok=True)
    return path


def migrate_data_from_project_root():
    """Move data written by older dev runs out of the repository.

    Called once at startup. Only moves a file when the destination is absent
    or older, so the copy the user has actually been using wins — which for
    this project was the repository one, and losing it would have looked like
    the app forgetting every account.

    Returns the names it moved, for the log.
    """
    import shutil

    target = get_data_dir()
    moved = []

    for name in DATA_FILES:
        source = os.path.join(_PROJECT_ROOT, name)
        if not os.path.isfile(source):
            continue
        destination = os.path.join(target, name)
        try:
            if os.path.exists(destination):
                if os.path.getmtime(destination) >= os.path.getmtime(source):
                    continue  # AppData already has the newer copy
                shutil.copy2(destination, destination + ".superseded")
            shutil.copy2(source, destination)
            os.replace(source, source + ".moved-to-appdata")
            moved.append(name)
        except OSError:
            # A locked or unreadable file must not stop the app starting.
            continue

    for name in DATA_DIRS:
        source = os.path.join(_PROJECT_ROOT, name)
        destination = os.path.join(target, name)
        if not os.path.isdir(source) or os.path.exists(destination):
            continue
        try:
            shutil.copytree(source, destination)
            os.replace(source, source + ".moved-to-appdata")
            moved.append(name + "/")
        except OSError:
            continue

    return moved
