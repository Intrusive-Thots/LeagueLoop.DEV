"""
Prove no control overflows its container, on every tab, at every panel width.

    python tools/check_overflow.py [--widths 380,480,620,900,1280]

Why this exists
---------------
`check_scaling.py` answers "does the UI survive Windows scaling", but it only
ever inspects the tab that happens to be on top: a `QStackedWidget` hides the
others, and hidden widgets have no meaningful geometry. Nine of the ten tabs
were therefore never measured by anything.

This walks every tab, at every width the companion panel can realistically be
dragged to, and reports any visible child whose geometry escapes its parent's
content rect — the champion tile poking past the grid, the button wider than
its card, the label running under the scrollbar.

It exits non-zero when anything clips, so it can gate a build.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Tuple

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Widths that matter: the narrowest the window can be dragged, the default
#: companion width, and a couple of comfortable desktop sizes.
DEFAULT_WIDTHS = (380, 480, 620, 900, 1280)
DEFAULT_HEIGHT = 720


def _settle(app, passes: int = 8) -> None:
    """Let layouts finish. One processEvents() is not enough for nested
    scroll areas, whose viewports resize in a later pass."""
    for _ in range(passes):
        app.sendPostedEvents()
        app.processEvents()


#: A widget narrower than its own minimum by more than this is squeezed.
#: One or two pixels is layout rounding; twenty is a clipped label.
SQUEEZE_TOLERANCE = 2


def find_squeezed(root) -> List[str]:
    """Every visible widget rendered smaller than its own minimum.

    Overflow is not the only way content gets lost. When a layout cannot
    satisfy its children it shrinks them *below* `minimumSizeHint()` instead,
    and Qt reports no error: the button is still inside its card, it is just
    four characters wide with an ellipsis. `find_clipping` sees nothing wrong
    with that, which is how a tab demanding 1162px inside 780px of window
    passed every check while looking broken on screen.
    """
    problems: List[str] = []
    stack = [root]
    while stack:
        widget = stack.pop()
        for child in widget.children():
            if not hasattr(child, "minimumSizeHint") or not hasattr(child, "isVisible"):
                continue
            if not child.isVisible():
                continue
            stack.append(child)
            wanted = child.minimumSizeHint()
            actual = child.size()
            short_w = wanted.width() - actual.width()
            short_h = wanted.height() - actual.height()
            if max(short_w, short_h) > SQUEEZE_TOLERANCE:
                text = getattr(child, "text", None)
                label = (text() if callable(text) else "") or child.objectName()
                problems.append(
                    "{} '{}' squeezed: wants {}x{}, given {}x{}".format(
                        child.metaObject().className(), label[:40],
                        wanted.width(), wanted.height(),
                        actual.width(), actual.height(),
                    )
                )
    return problems


def check_tab(window, key: str, width: int, app, out_dir: str) -> List[str]:
    """Show one tab at one width and report what does not fit."""
    from check_scaling import find_clipping

    window.resize(width, DEFAULT_HEIGHT)
    button = window.sidebar.buttons.get(key)
    if button is not None:
        button.click()
    _settle(app)

    page = window.tab_stack.currentWidget()
    # Report the width Qt actually granted: below the window's minimum the
    # request is ignored, and blaming a failure on a width that was never
    # applied wastes an afternoon.
    actual_width = window.width()
    found = find_clipping(page) + find_squeezed(page)
    problems = [
        "[{} @ {}px] {}".format(key, actual_width, p) for p in found
    ]

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        page.grab().save(os.path.join(out_dir, "{}_{}.png".format(key, width)))
    return problems


def run(widths: Tuple[int, ...], out_dir: str) -> List[str]:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from ui.qt.main_window import LeagueLoopMainWindow

    window = LeagueLoopMainWindow(container=None)
    window.show()
    _settle(app)

    problems: List[str] = []
    for width in widths:
        for key, _name, _icon in window.sidebar.DEFAULT_TABS:
            problems.extend(check_tab(window, key, width, app, out_dir))
    window.close()
    return problems


#: Windows scaling factors to sweep. Layout minimums change with the DPI, so
#: a tab that fits at 100% can overflow at 175% without a line of code
#: changing.
SCALES = (1.0, 1.25, 1.5, 1.75, 2.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--widths", default=",".join(str(w) for w in DEFAULT_WIDTHS))
    parser.add_argument("--out", default="build/overflow")
    parser.add_argument(
        "--all-scales", action="store_true",
        help="Re-run at every Windows scaling factor (100%%-200%%).",
    )
    args = parser.parse_args()

    if args.all_scales:
        # QT_SCALE_FACTOR is read once, when QGuiApplication is constructed,
        # so one process cannot cover several factors.
        import subprocess

        failed = False
        for scale in SCALES:
            env = dict(os.environ, QT_SCALE_FACTOR=str(scale))
            result = subprocess.run(
                [sys.executable, os.path.abspath(__file__),
                 "--widths", args.widths,
                 "--out", os.path.join(args.out, str(scale).replace(".", "_"))],
                env=env, capture_output=True, text=True,
            )
            print("{:>5}x  {}".format(
                scale, (result.stdout.strip().splitlines() or [""])[0]))
            for line in result.stdout.strip().splitlines()[1:]:
                print("        " + line.strip())
            failed = failed or result.returncode != 0
        return 1 if failed else 0

    widths = tuple(int(w) for w in args.widths.split(",") if w.strip())
    problems = run(widths, args.out)
    if problems:
        print("{} overflowing control(s):".format(len(problems)))
        for problem in problems:
            print("  " + problem)
        return 1
    print("no overflow at widths {}".format(", ".join(str(w) for w in widths)))
    return 0


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(os.path.dirname(here), "src"))
    sys.path.insert(0, here)
    sys.exit(main())
