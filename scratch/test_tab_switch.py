import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "src"))

import customtkinter as ctk
from core.main import LeagueLoopApp
from PySide6.QtWidgets import QApplication
from ui.qt.app_window import LeagueLoopQtWindow
from PySide6.QtCore import QTimer

try:
    print("Initializing CustomTkinter App...")
    app = LeagueLoopApp()
    
    print("Initializing PySide6 App...")
    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_window = LeagueLoopQtWindow()
    qt_window.show()
    
    print("Setting up QTimer...")
    timer = QTimer()
    
    def pump_tkinter():
        try:
            if app.winfo_exists():
                app.update()
        except Exception as e:
            import traceback
            err_str = traceback.format_exc()
            print(f"Exception in Tkinter event pump:\n{err_str}")

    timer.timeout.connect(pump_tkinter)
    timer.start(16)
    
    # Let's run the Qt event loop for 1.5 seconds to initialize
    print("Running event loop for initial render...")
    start_time = time.time()
    while time.time() - start_time < 1.5:
        qt_app.processEvents()
        time.sleep(0.01)
        
    print("Switching tab to Automations...")
    app.sidebar.switch_tab("Automations")
    
    # Run the event loop for another 3 seconds to see if it crashes or errors out
    print("Running event loop after tab switch...")
    start_time = time.time()
    while time.time() - start_time < 3.0:
        qt_app.processEvents()
        time.sleep(0.01)
        
    print("Successfully completed without crash!")
    app.destroy()
    qt_window.close()
except Exception as e:
    import traceback
    print("CRASHED WITH ERROR:")
    traceback.print_exc()
    sys.exit(1)
