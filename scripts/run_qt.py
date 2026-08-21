"""
Development entry point for the PySide6 shell.

The production entry point is still `run.py` (CustomTkinter). Per UI/UX
Master Plan §73 the two shells run side by side until the Qt surfaces are
validated, and only then is the old UI removed (Stage 10).

Usage
-----
    python run_qt.py                     # full app, real services
    python run_qt.py --no-services       # UI only, never touches the LCU
    python run_qt.py --screenshot out.png
                                         # render offscreen and exit (§70)
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the LeagueLoop Qt shell.")
    parser.add_argument(
        "--no-services",
        action="store_true",
        help="Run the UI without building the service container (no LCU access).",
    )
    parser.add_argument(
        "--screenshot",
        metavar="PATH",
        help="Render the window to PATH and exit. Implies --no-services.",
    )
    parser.add_argument(
        "--size",
        metavar="WxH",
        default="980x660",
        help="Window size for --screenshot (default: 980x660).",
    )
    args = parser.parse_args()

    if args.screenshot:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    if sys.platform == "win32":
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor v2
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    from ui.qt.app.application import build, run

    if args.screenshot:
        app, window, _container = build(with_services=False)
        try:
            width, height = (int(v) for v in args.size.lower().split("x"))
            window.resize(width, height)
        except Exception:
            pass
        window.show()
        # Flush pending layout work so the capture is not taken mid-relayout.
        for _ in range(5):
            app.sendPostedEvents()
            app.processEvents()
        window.grab().save(args.screenshot)
        print(f"Saved screenshot to {args.screenshot}")
        return 0

    return run(with_services=not args.no_services)


if __name__ == "__main__":
    raise SystemExit(main())
