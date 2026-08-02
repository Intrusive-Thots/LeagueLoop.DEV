import sys
import os

# Ensure the root project directory is in the Python path
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))

if __name__ == "__main__":
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        pass
        
    from core.main import LeagueLoopApp, _kill_other_instances
    _kill_other_instances()
    app = LeagueLoopApp()
    app.mainloop()
