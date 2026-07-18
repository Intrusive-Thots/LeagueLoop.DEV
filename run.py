import sys
import os

# Ensure the root project directory is in the Python path
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))

import traceback
from utils.logger import Logger

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
    err_str = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    Logger.error("SYS", f"Uncaught thread exception in thread {args.thread.name}:\n{err_str}")

threading.excepthook = global_thread_exception_handler

if __name__ == "__main__":
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        pass
        
    from core.main import LeagueLoopApp, _kill_other_instances
    _kill_other_instances()
    
    # Initialize CustomTkinter app
    app = LeagueLoopApp()
    
    # Initialize PySide6 QApplication and window shell
    from PySide6.QtWidgets import QApplication
    from ui.qt.app_window import LeagueLoopQtWindow
    
    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_window = LeagueLoopQtWindow(app)
    qt_window.show()
    
    # Setup QTimer to pump the Tkinter event loop on the main thread
    from PySide6.QtCore import QTimer
    timer = QTimer()
    
    def pump_tkinter():
        try:
            if app.winfo_exists():
                app.update()
        except Exception as e:
            import traceback
            err_str = traceback.format_exc()
            Logger.error("SYS", f"Exception in Tkinter event pump:\n{err_str}")

    timer.timeout.connect(pump_tkinter)
    timer.start(16)  # ~60 FPS
    
    # Handle clean termination of CTk app when Qt app exits
    def on_qt_quit():
        try:
            app._on_close()
        except Exception:
            pass
    qt_app.aboutToQuit.connect(on_qt_quit)
    
    # Run the PySide6 event loop (main thread driver)
    sys.exit(qt_app.exec())
