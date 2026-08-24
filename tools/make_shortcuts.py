"""
Build the LeagueLoop desktop shortcuts.

    python tools/make_shortcuts.py [output_dir]

Why this exists rather than a PowerShell one-liner
--------------------------------------------------
The usual way to make a .lnk on Windows is `WScript.Shell.CreateShortcut`.
That is fine when you are sitting at the machine, but it also stamps the
shortcut with a *link-tracking* record — machine name, volume id, object id.
The previous `Development Launcher.lnk` had one pointing at
`\\\\MYDESKTOP\\Users\\Administrator\\LeagueLoop.DEV\\launch_dev.bat`: a user
profile that no longer exists, reached over UNC. Windows tries to resolve
that before falling back, which is why the shortcut sat there and then failed.

Building the file directly gives a shortcut with no tracking record at all —
just a target, a working directory and an icon.

The bug this file works around
------------------------------
`pylnk3.PathSegmentEntry.create_for_path` decides whether a path segment is a
folder or a file with::

    entry.type = os.path.isdir(path) and TYPE_FOLDER or TYPE_FILE

That is evaluated on the machine *running the generator*. These shortcuts are
built in a Linux container, where `C:\\Users\\Malcolm\\...` does not exist, so
`isdir` is False for every segment and the whole path is typed as files
(shell item `0x32`). Windows needs `0x31` for directories and `0x32` only for
the leaf; a path whose intermediate items claim to be files cannot be walked
by Explorer, and since `for_file` also leaves `link_info` unset there is no
LinkInfo block to fall back on. The result is a shortcut that does nothing at
all when double-clicked, with no error.

`_path_id_list` therefore builds the list itself and types each entry from
its position, not from the local filesystem. `verify` re-reads the finished
file and asserts the byte pattern, so this cannot regress silently.
"""
from __future__ import annotations

import os
import struct
import sys

import pylnk3

ROOT = r"C:\Users\Malcolm\LeagueLoop.DEV"
#: The icon a new shortcut points at. `make_icon.py` writes a content-stamped
#: `icon-<hash>.ico` alongside the fixed names, and pointing at that is what
#: makes a changed icon actually appear: Explorer caches shortcut icons by
#: path, so a shortcut re-pointed at the same filename keeps showing the old
#: artwork however many times the file is rewritten.
def _icon_name() -> str:
    """The icon filename to write into the shortcut.

    The *name* is discovered from this checkout's `assets/`, because that is
    the directory this script can actually read; the path written into the
    .lnk is always the Windows one under `ROOT`. Building the shortcut on one
    machine for another is the normal case here, so those two must not be the
    same lookup.
    """
    here = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets",
    )
    try:
        stamped = sorted(
            name for name in os.listdir(here)
            if name.startswith("icon-") and name.endswith(".ico")
        )
    except OSError:
        stamped = []
    return stamped[-1] if stamped else "leagueloop.ico"


ICON = ROOT + r"\assets" + "\\" + _icon_name()

#: (filename, target relative to ROOT, description)
SHORTCUTS = (
    # One shell, one shortcut. The Qt build and its "LeagueLoop (old UI)"
    # counterpart are both gone; anything still pointing at
    # `launch_qt_dev.bat` now points at nothing.
    ("LeagueLoop.lnk", "launch_dev.bat", "LeagueLoop"),
)

HEADER_SIZE = 0x4C
FLAG_HAS_LINK_TARGET_IDLIST = 0x01

TYPE_DIRECTORY = 0x31
TYPE_FILE = 0x32


def _path_id_list(target: str) -> "pylnk3.LinkTargetIDList":
    """Build the target's shell ID list with correct folder/file typing.

    Every element except the last is a directory. That is knowable from the
    path alone and must not be probed on the local filesystem.
    """
    levels = list(pylnk3.path_levels(target))
    elements = [
        pylnk3.RootEntry(pylnk3.ROOT_MY_COMPUTER),
        pylnk3.DriveEntry(levels[0]),
    ]
    for index, level in enumerate(levels[1:]):
        entry = pylnk3.PathSegmentEntry.create_for_path(level)
        is_leaf = index == len(levels) - 2
        entry.type = pylnk3.TYPE_FILE if is_leaf else pylnk3.TYPE_FOLDER
        elements.append(entry)

    id_list = pylnk3.LinkTargetIDList()
    id_list.items = elements
    return id_list


def item_types(path: str) -> list:
    """The shell item type bytes of a finished shortcut, in order."""
    data = open(path, "rb").read()
    size = struct.unpack("<H", data[HEADER_SIZE:HEADER_SIZE + 2])[0]
    blob = data[HEADER_SIZE + 2:HEADER_SIZE + 2 + size]
    types, i = [], 0
    while i < len(blob) - 1:
        item = struct.unpack("<H", blob[i:i + 2])[0]
        if item == 0:
            break
        types.append(blob[i + 2])
        i += item
    return types


def verify(path: str) -> None:
    """Fail loudly if the shortcut is not shaped like one Windows will run."""
    types = item_types(path)
    if len(types) < 3:
        raise AssertionError(f"{path}: target path is too short to be valid")
    if types[-1] != TYPE_FILE:
        raise AssertionError(
            f"{path}: leaf is 0x{types[-1]:02x}, expected 0x{TYPE_FILE:02x}"
        )
    bad = [f"#{i} 0x{t:02x}" for i, t in enumerate(types[2:-1], start=2)
           if t != TYPE_DIRECTORY]
    if bad:
        raise AssertionError(
            f"{path}: these path segments are not typed as directories: "
            + ", ".join(bad)
        )


def build(out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for filename, target, description in SHORTCUTS:
        path = os.path.join(out_dir, filename)
        full_target = ROOT + "\\" + target
        lnk = pylnk3.for_file(
            full_target,
            lnk_name=None,
            work_dir=ROOT,
            description=description,
            icon_file=ICON,
            icon_index=0,
        )
        lnk.shell_item_id_list = _path_id_list(full_target)
        with open(path, "wb") as handle:
            lnk.save(handle)
        verify(path)
        written.append(path)
        print(f"{filename:26s} -> {target}   "
              + " ".join(f"0x{t:02x}" for t in item_types(path)))
    return written


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "build/shortcuts"
    build(out)
    print("\nAll shortcuts verified: directories 0x31, leaf 0x32.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
