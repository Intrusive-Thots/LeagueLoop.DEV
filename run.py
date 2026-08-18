import os
import sys

# Ensure the root project directory is in the Python path
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))

USAGE = """LeagueLoop

  python run.py              start LeagueLoop (CustomTkinter)
  python run.py --qt         start LeagueLoop (PySide6 Qt Shell)
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

    if "--qt" in args:
        from ui.qt.app.application import run as run_qt_app
        raise SystemExit(run_qt_app(with_services="--no-services" not in args))

    replace = "--replace" in args or "--force" in args

    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        pass

    from core.main import (  # type: ignore
        LeagueLoopApp,
        _find_other_instances,
        _kill_other_instances,
    )

    # Single instance. Previously this terminated whatever was already
    # running, which meant launching a second time silently killed the copy
    # you were using - the old window just reported "exit code 15". Now we
    # refuse and say so, and taking over is opt-in via --replace.
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
            # Exit 0: this is a normal outcome, not a failure. Exiting non-zero
            # here is what made launchers report a crash.
            raise SystemExit(0)

    app = LeagueLoopApp()
    app.mainloop()
