"""
Entry point for the LeagueLoop application (CustomTkinter).

Installs crash handlers, logs session startup/summary, and launches LeagueLoopApp.
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
