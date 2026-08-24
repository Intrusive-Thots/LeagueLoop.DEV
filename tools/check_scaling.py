"""
Render Qt surfaces at every Windows scaling factor and prove nothing clips.

    python tools/check_scaling.py [--out DIR]

Why this exists
---------------
"Looks fine on my machine" is not a claim anyone can check, and eyeballing a
screenshot does not catch a button whose right edge is four pixels past its
card. This walks the actual widget tree after layout has settled and reports
any child whose geometry escapes its parent, at each scale factor.

It exits non-zero if anything clips, so it can gate a build.

Qt is told to scale via `QT_SCALE_FACTOR`, which is what Windows per-monitor
DPI does to the application in practice. `PassThrough` rounding is left alone
— that is the policy the app ships with, and testing under a different one
would be testing something the user never runs.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Tuple

# Offscreen before Qt is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SCALES = (1.0, 1.25, 1.5, 1.75, 2.0)

#: Widgets whose overflow is expected and handled by a scroll area.
SCROLLABLE = ("QScrollArea", "QListWidget", "QPlainTextEdit", "QTextEdit",
              "QTableWidget", "QTableView", "QTreeWidget", "QTreeView")


def _is_scroll_container(widget) -> bool:
    """True when children are *supposed* to overflow this widget.

    Two cases, and the second is the one that produced a page of false
    positives: a `QScrollArea` does not parent its content directly. The real
    hierarchy is `QScrollArea > qt_scrollarea_viewport > content`, so the
    content widget's parent is an anonymous `QWidget` that looks like any
    other. A scroll area whose content is taller than the viewport is the
    scroll area doing its job, not a clipped control.
    """
    if widget.metaObject().className() in SCROLLABLE:
        return True
    if widget.objectName() == "qt_scrollarea_viewport":
        return True
    parent = widget.parentWidget() if hasattr(widget, "parentWidget") else None
    if parent is not None and hasattr(parent, "viewport"):
        try:
            return parent.viewport() is widget
        except Exception:
            return False
    return False


def _escapes(child, parent) -> Tuple[int, int, int, int]:
    """How far a child pokes out of its parent, per edge. Zeros mean fine."""
    inner = parent.contentsRect()
    geom = child.geometry()
    return (
        max(0, inner.left() - geom.left()),
        max(0, inner.top() - geom.top()),
        max(0, geom.right() - inner.right()),
        max(0, geom.bottom() - inner.bottom()),
    )


def find_clipping(root, tolerance: int = 1) -> List[str]:
    """Every visible child that does not fit inside its parent.

    `tolerance` absorbs sub-pixel rounding at fractional scale factors; a
    genuine clip is many pixels, not one.
    """
    problems: List[str] = []
    stack = [root]
    while stack:
        parent = stack.pop()
        scrollable = _is_scroll_container(parent)
        for child in parent.children():
            if not hasattr(child, "geometry") or not hasattr(child, "isVisible"):
                continue
            if not child.isVisible():
                continue
            stack.append(child)
            if scrollable:
                continue  # overflow here is the whole point of a scroll area
            left, top, right, bottom = _escapes(child, parent)
            worst = max(left, top, right, bottom)
            if worst > tolerance:
                problems.append(
                    "{} inside {}: over by L{} T{} R{} B{} "
                    "(child {}, parent content {})".format(
                        child.metaObject().className(),
                        parent.metaObject().className(),
                        left, top, right, bottom,
                        child.geometry().getRect(),
                        parent.contentsRect().getRect(),
                    )
                )
    return problems


def _build(kind: str, app):
    """Construct the surface under test, with no services attached."""
    if kind == "orb":
        from ui.qt.widgets.orb_widget import QtOrbWidget

        widget = QtOrbWidget()
        return widget
    from ui.qt.main_window import LeagueLoopMainWindow

    window = LeagueLoopMainWindow(container=None)
    window.resize(1000, 680)
    return window


def render(kind: str, scale: float, out_dir: str) -> List[str]:
    """Render one surface at one scale. Returns any clipping found."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    widget = _build(kind, app)
    widget.show()
    for _ in range(6):
        app.sendPostedEvents()
        app.processEvents()

    problems = find_clipping(widget)

    os.makedirs(out_dir, exist_ok=True)
    name = "{}_{}x.png".format(kind, str(scale).replace(".", "_"))
    widget.grab().save(os.path.join(out_dir, name))

    widget.close()
    widget.deleteLater()
    app.processEvents()
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="build/scaling")
    parser.add_argument("--surface", default="orb", choices=("orb", "window"))
    parser.add_argument("--scale", type=float, default=None)
    args = parser.parse_args()

    scale = args.scale
    if scale is None:
        # Re-exec once per scale: QT_SCALE_FACTOR is read when QGuiApplication
        # is constructed, so one process cannot cover several factors.
        import subprocess

        failed = False
        for value in SCALES:
            env = dict(os.environ, QT_SCALE_FACTOR=str(value))
            result = subprocess.run(
                [sys.executable, __file__, "--out", args.out,
                 "--surface", args.surface, "--scale", str(value)],
                env=env, capture_output=True, text=True,
            )
            sys.stdout.write(result.stdout)
            if result.returncode != 0:
                failed = True
                sys.stderr.write(result.stderr)
        return 1 if failed else 0

    problems = render(args.surface, scale, args.out)
    label = "{:>5}x {:<7}".format(scale, args.surface)
    if problems:
        print("{}  {} CLIPPED".format(label, len(problems)))
        for problem in problems:
            print("        " + problem)
        return 1
    print("{}  clean".format(label))
    return 0


if __name__ == "__main__":
    sys.path.insert(
        0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
    )
    sys.exit(main())
