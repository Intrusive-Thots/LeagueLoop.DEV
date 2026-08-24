"""
Every asset the code asks for must actually be there.

Two bugs of the same shape, both invisible at runtime:

* `app_sidebar` asked for `logo.png` and fell back to `icon.png` — neither
  had the `assets/` prefix, so neither path has ever existed and the header
  has been running without its logo. Nothing raised; the label was simply
  never created.
* `get_asset_path` resolved against `os.path.abspath(".")`, so every asset
  path was correct only when the app happened to be launched from the
  repository root. A shortcut with a different "Start in" folder resolved
  every icon and champion portrait to a path that did not exist.

Neither could fail loudly, because a missing image is an `if os.path.exists`
away from being nothing at all. So they are checked here instead.
"""
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

#: `get_asset_path("...")` with a literal string argument.
ASSET_CALL = re.compile(r"""get_asset_path\(\s*["']([^"']+)["']\s*\)""")

#: Sizes Windows picks between for the taskbar, Alt-Tab, the title bar and
#: the desktop. A single-size .ico is upscaled for the rest, and an upscaled
#: 32px icon is the blurry one people notice.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


class AssetPathTests(unittest.TestCase):
    def test_paths_resolve_from_anywhere_not_just_the_repo_root(self):
        from utils.path_utils import get_asset_path

        here = os.getcwd()
        try:
            os.chdir(os.path.dirname(here) or "/")
            resolved = get_asset_path("assets/app.ico")
            self.assertTrue(
                os.path.exists(resolved),
                "assets stop resolving when the working directory changes: %s"
                % resolved,
            )
        finally:
            os.chdir(here)

    def test_every_literal_asset_the_code_asks_for_exists(self):
        """The check that would have caught the missing logo."""
        from utils.path_utils import get_asset_path

        missing = []
        for path in sorted(SRC.rglob("*.py")):
            body = path.read_text(encoding="utf-8-sig", errors="replace")
            for asked in ASSET_CALL.findall(body):
                if not os.path.exists(get_asset_path(asked)):
                    missing.append("%s asks for %r" % (path.name, asked))
        self.assertEqual(missing, [], "\n  ".join([""] + missing))


class IconTests(unittest.TestCase):
    ASSETS = ROOT / "assets"

    def test_the_ico_carries_every_size_windows_asks_for(self):
        from PIL import Image

        for name in ("app.ico", "leagueloop.ico"):
            with Image.open(self.ASSETS / name) as image:
                sizes = {size[0] for size in image.info.get("sizes", ())}
            for expected in ICO_SIZES:
                self.assertIn(expected, sizes, "%s has no %dpx image" % (name, expected))

    def test_a_content_stamped_icon_exists(self):
        """Explorer caches a shortcut's icon by path, so rewriting
        `leagueloop.ico` in place leaves the previous artwork on the desktop.
        A filename that changes with the artwork is what makes a new icon
        appear."""
        stamped = list(self.ASSETS.glob("icon-*.ico"))
        self.assertEqual(
            len(stamped), 1,
            "expected exactly one stamped icon, found %s"
            % [p.name for p in stamped],
        )

    def test_the_stamp_matches_the_artwork(self):
        import hashlib

        from PIL import Image

        stamped = next(self.ASSETS.glob("icon-*.ico"))
        with Image.open(self.ASSETS / "app_icon.png") as master:
            digest = hashlib.sha256(master.tobytes()).hexdigest()[:8]
        self.assertEqual(
            stamped.stem, "icon-" + digest,
            "the stamped filename does not match the current artwork, so a "
            "shortcut pointing at it would show a stale icon",
        )

    def test_the_shortcut_points_at_the_stamped_icon(self):
        """Read as source rather than imported: `make_shortcuts` needs
        `pylnk3`, which is only installed where shortcuts are actually
        built, and this assertion does not need it."""
        body = (ROOT / "tools" / "make_shortcuts.py").read_text(encoding="utf-8")
        self.assertIn("_icon_name()", body)
        self.assertIn('name.startswith("icon-")', body)
        self.assertNotIn(
            'ICON = ROOT + r"\\assets\\leagueloop.ico"', body,
            "shortcuts point at a fixed filename, which Explorer serves from "
            "its icon cache",
        )

    def test_the_idle_and_active_tray_icons_differ(self):
        """They are the same mark; only the play glyph's colour changes. If
        they were identical the tray could not show whether anything is
        running."""
        from PIL import Image

        with Image.open(self.ASSETS / "icon_active.png") as active:
            with Image.open(self.ASSETS / "icon_idle.png") as idle:
                self.assertNotEqual(active.tobytes(), idle.tobytes())


if __name__ == "__main__":
    unittest.main()
