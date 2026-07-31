import sys
import os

# Ensure the root project directory is in the Python path
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))

import traceback
import warnings
import urllib3
from utils.logger import Logger

# The League Client uses a self-signed cert on localhost — suppress the noise.
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)


def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Global exception handler."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    err_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    Logger.error("SYS", f"Uncaught exception:\n{err_str}")


sys.excepthook = global_exception_handler

import threading


def global_thread_exception_handler(args):
    """Global thread exception handler."""
    if issubclass(args.exc_type, KeyboardInterrupt):
        return
    err_str = "".join(traceback.format_exception(
        args.exc_type, args.exc_value, args.exc_traceback
    ))
    Logger.error(
        "SYS",
        f"Uncaught thread exception in thread {args.thread.name}:\n{err_str}"
    )


threading.excepthook = global_thread_exception_handler

if __name__ == "__main__":
    # Enable faulthandler to capture C-level crashes (segfaults) to stderr
    import faulthandler
    faulthandler.enable()

    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        pass

    from core.main import LeagueLoopApp, _kill_other_instances
    _kill_other_instances()

    # Initialize LeagueLoop core application controller
    app = LeagueLoopApp()

    # Initialize PySide6 QApplication and window shell
    from PySide6.QtWidgets import QApplication
    from ui.qt.app_window import LeagueLoopQtWindow

    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_window = LeagueLoopQtWindow(app)
    qt_window.show()

    # Handle clean termination: stop core app on quit
    def on_qt_quit():
        try:
            app._on_close()
        except Exception:  # noqa: BLE001
            pass

    qt_app.aboutToQuit.connect(on_qt_quit)

    # Run the PySide6 event loop (main thread driver)
    try:
        exit_code = qt_app.exec()
    except Exception as e:  # noqa: BLE001
        Logger.error("SYS", f"Qt event loop crashed: {e}")
        exit_code = 1

    sys.exit(exit_code)

