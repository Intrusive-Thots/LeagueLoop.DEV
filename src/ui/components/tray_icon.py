import threading
from PIL import Image
import pystray # type: ignore
from pystray import MenuItem as item # type: ignore
from utils.path_utils import get_asset_path # type: ignore
from utils.logger import Logger # type: ignore

class SystemTrayApp:
    def __init__(self, app_root):
        """
        Manages the custom System Tray icon using pystray.
        :param app_root: The main CustomTkinter base window.
        """
        self.app_root = app_root
        self.icon = None
        self._thread = None
        self._is_running = False

    def start(self):
        """Spawns the tray icon in a dedicated daemon thread."""
        if self._is_running:
            return
            
        self._is_running = True
        self._thread = threading.Thread(target=self._run_icon, daemon=True)
        self._thread.start()
        Logger.info("TrayIcon", "System tray icon spawned.")

    def _run_icon(self):
        try:
            icon_path = get_asset_path("assets/app.ico")
            try:
                image = Image.open(icon_path)
            except Exception as e:
                # Fallback blank image if strictly missing
                image = Image.new('RGB', (64, 64), color=(30, 35, 40))
                Logger.warning("TrayIcon", f"Failed to load app icon: {e}")

            menu = pystray.Menu(
                item('Show LeagueLoop', self._show_window, default=True),
                pystray.Menu.SEPARATOR,
                item('Settings', self._open_settings),
                item('Quit', self._quit_app)
            )

            self.icon = pystray.Icon(
                "LeagueLoop", 
                image, 
                "LeagueLoop Tracker", 
                menu=menu
            )
            self.icon.run()
        except Exception as e:
            Logger.error("TrayIcon", f"Tray icon crashed: {e}")
            self._is_running = False

    def stop(self):
        """Safely stops and unregisters the tray icon."""
        self._is_running = False
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

    # --- Actions ---
    
    def _show_window(self, icon=None, item=None):
        """Restores the main UI and lifts it to the foreground."""
        try:
            # We schedule this into the Tkinter mainloop to prevent cross-thread violations
            if hasattr(self.app_root, "after"):
                self.app_root.after(0, self._sync_show)
        except Exception as e:
            Logger.error("TrayIcon", str(e))

    def _sync_show(self):
        self.app_root.deiconify()
        self.app_root.lift()
        self.app_root.focus_force()

    def _open_settings(self, icon=None, item=None):
        try:
            if hasattr(self.app_root, "after") and hasattr(self.app_root, "sidebar"):
                if hasattr(self.app_root.sidebar, "switch_tab"):
                    self.app_root.after(0, lambda: self.app_root.sidebar.switch_tab("Settings"))
                    self.app_root.after(50, self._sync_show)
        except Exception:
            pass

    def _quit_app(self, icon=None, item=None):
        try:
            if hasattr(self.app_root, "after"):
                # Call the actual destroy method of the Tk root
                self.app_root.after(0, self.app_root.destroy)
        except Exception:
            pass
