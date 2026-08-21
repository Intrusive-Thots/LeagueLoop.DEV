import os
import sys

# Ensure the root project directory is in the Python path
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))

USAGE = """LeagueLoop

  python run.py              start LeagueLoop (PySide6 Qt Shell - Default)
  python run.py --tk         start LeagueLoop (Legacy CustomTkinter)
  python run.py --replace    shut down a running instance and start fresh
  python run.py --help       show this message
"""


def _describe(proc):
    """Best-effort one-line description of another instance."""
    try:
        return "PID {} ({})".format(proc.pid, proc.name())
    except Exception:
        return "PID {}".format(getattr(proc, "pid", "?"))


if __name__ == "__main__":
    args = [a.lower() for a in sys.argv[1:]]

    if "--help" in args or "-h" in args:
        print(USAGE)
        raise SystemExit(0)

    replace = "--replace" in args or "--force" in args

    import ctypes
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor v2
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    from core.main import (  # type: ignore
        _find_other_instances,
        _kill_other_instances,
    )

    # Single instance check
    others = _find_other_instances()
    if others:
        if replace:
            killed = _kill_other_instances()
            print(
                "Replaced {} running LeagueLoop instance(s): {}".format(
                    len(killed), ", ".join(str(p) for p in killed)
                )
            )
        else:
            print("LeagueLoop is already running:")
            for proc in others:
                print("    " + _describe(proc))
            print()
            print("Not starting a second copy.")
            print("The running instance may be minimised to the system tray -")
            print("exit it from there, or start fresh with:")
            print()
            print("    python run.py --replace")
            raise SystemExit(0)

    use_legacy_tk = "--tk" in args or "--legacy" in args or "--customtkinter" in args

    if use_legacy_tk:
        from core.main import LeagueLoopApp
        app = LeagueLoopApp()
        app.mainloop()
    else:
        from ui.qt.app.application import run as run_qt_app
        raise SystemExit(run_qt_app(with_services="--no-services" not in args))
