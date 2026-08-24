"""
Entry point for the CustomTkinter shell.

The Qt shell (`run_qt.py`) is the one under active development; this one is
kept until the migration finishes. Both install the same crash handlers and
write to the same log directory, so a run of either leaves a complete record.
"""
import os
import sys

# Ensure the root project directory is in the Python path
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))

if __name__ == "__main__":
    import ctypes

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        pass

    from utils.logger import Logger, prune_old_logs
    from utils.session_log import (
        install_crash_handlers,
        session_banner,
        session_summary,
    )

    install_crash_handlers()
    session_banner(shell="customtkinter", argv=sys.argv[1:])

    try:
        from core.main import LeagueLoopApp, _kill_other_instances

        _kill_other_instances()
        app = LeagueLoopApp()
        app.mainloop()
    except Exception as exc:
        Logger.critical("Startup", "The application stopped with an error.", exc=exc)
        session_summary(reason=f"crash: {type(exc).__name__}")
        raise
    else:
        prune_old_logs()
        session_summary(reason="normal exit")
