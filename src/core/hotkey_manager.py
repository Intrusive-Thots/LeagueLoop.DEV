"""
Hotkey Manager Mixin
────────────────────
Extracted from main.py — handles global hotkey registration and all
hotkey-triggered actions (launch client, find match, toggle automation,
queue roulette, restart UX, account switching).
"""
import os
import random
import subprocess
import threading
import ctypes
import keyboard  # type: ignore

from PySide6.QtCore import QTimer

from utils.logger import Logger
from core.events import EventBus

class HotkeyManagerMixin:
    """Mixin providing hotkey registration and action handlers for LeagueLoopApp."""

    def after(self, ms: int, func):
        """Bridge method for legacy Tkinter .after() calls using QTimer.singleShot."""
        QTimer.singleShot(int(ms), func)

    def _bind_hotkeys(self):
        try:
            keyboard.unhook_all()
        except Exception as e:
            Logger.debug("SYS", f"Failed to unhook hotkeys: {e}")

        self._launch_hotkey = self.config.get("hotkey_launch_client", "ctrl+shift+l")
        self._automation_hotkey = self.config.get("hotkey_toggle_automation", "ctrl+shift+a")
        self._queue_hotkey = self.config.get("hotkey_find_match", "ctrl+shift+f")

        try:
            keyboard.add_hotkey(self._launch_hotkey, self._hotkey_launch_client, suppress=False)
            keyboard.add_hotkey(self._automation_hotkey, self._hotkey_toggle_automation, suppress=False)
            keyboard.add_hotkey(self._queue_hotkey, self._hotkey_find_match, suppress=False)
            Logger.info("SYS", f"Hotkeys registered: launch={self._launch_hotkey}, auto={self._automation_hotkey}, queue={self._queue_hotkey}")
        except Exception as e:
            Logger.error("SYS", f"Failed to register hotkeys: {e}")

    def _hotkey_find_match(self):
        """Invokes the match finder via global hotkey registration."""
        Logger.info("SYS", "Hotkey trigger: Find Match")
        if hasattr(self, "queue_service") and self.queue_service:
            threading.Thread(target=self.queue_service.find_match, daemon=True).start()

    def _hotkey_toggle_automation(self):
        Logger.info("SYS", "Hotkey trigger: Toggle Automation")
        is_paused = self.automation.paused if self.automation else True
        self.toggle_power(is_paused)

    def _hotkey_launch_client(self):
        def _launch():
            path_override = self.config.get("league_path_override", "")
            if path_override and os.path.exists(path_override):
                candidates = [path_override]
            else:
                candidates = []
                try:
                    from utils.client_detector import resolve_installation_paths
                    _, rc_install_dir = resolve_installation_paths()
                    if rc_install_dir:
                        rc_path = os.path.join(rc_install_dir, "RiotClientServices.exe")
                        if os.path.exists(rc_path):
                            candidates.append(rc_path)
                except Exception as e:
                    Logger.debug("SYS", f"Failed resolving installs: {e}")

                candidates.extend([
                    r"C:\Riot Games\Riot Client\RiotClientServices.exe",
                    r"D:\Riot Games\Riot Client\RiotClientServices.exe",
                    r"E:\Riot Games\Riot Client\RiotClientServices.exe",
                    r"C:\Program Files (x86)\Riot Games\Riot Client\RiotClientServices.exe",
                    os.path.join(os.environ.get("USERPROFILE", ""), r"Riot Games\Riot Client\RiotClientServices.exe")
                ])

                # Proactive Registry Lookup
                try:
                    import winreg
                    for hkey in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
                        try:
                            key = winreg.OpenKey(hkey, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game league_of_legends.live")
                            val, _ = winreg.QueryValueEx(key, "UninstallString")
                            if val and "RiotClientServices.exe" in val:
                                path = val.split('"')[1] if '"' in val else val.split(' ')[0]
                                if os.path.exists(path): candidates.insert(0, path)
                        except FileNotFoundError:
                            pass
                        except Exception as e:
                            Logger.debug("SYS", f"Registry iteration failed: {e}")
                except Exception as e:
                    Logger.debug("SYS", f"Registry module failed: {e}")

            for c in candidates:
                if os.path.exists(c):
                    Logger.info("SYS", "Launching Riot Client...")
                    args = "--launch-product=league_of_legends --launch-patchline=live"
                    try:
                        ret = ctypes.windll.shell32.ShellExecuteW(
                            None, "open", c, args, None, 1
                        )
                        if ret <= 32:
                            subprocess.Popen([c] + args.split(), creationflags=subprocess.CREATE_NO_WINDOW)
                    except Exception:
                        try:
                            subprocess.Popen([c] + args.split(), creationflags=subprocess.CREATE_NO_WINDOW)
                        except OSError:
                            ctypes.windll.shell32.ShellExecuteW(
                                None, "runas", c, args, None, 1
                            )
                    return
            Logger.error("SYS", "Error: Could not find Riot Client.")
        self.after(0, _launch)

    def _switch_account_by_label(self, label):
        """Switch to an account identified by its label."""
        if not hasattr(self, "account_manager"):
            return
        for i, acct in enumerate(self.account_manager.get_accounts()):
            if acct.get("label", "") == label:
                self.account_manager.login_account(i, log_func=Logger.info)
                return

    def _quick_queue(self, mode_name):
        self.config.set("queue_mode", mode_name)
        self.after(50, self._hotkey_find_match)
        EventBus.emit("show_toast", f"Queued up for {mode_name}!", "🎮", 3000, "success")

    def _queue_roulette(self):
        modes = [
            "Quickplay", "Draft Pick", "Ranked Solo/Duo", "Ranked Flex",
            "ARAM", "Arena", "Brawl", "TFT Normal"
        ]

        if hasattr(self, "automation") and self.automation and not self.automation.paused:
            self.toggle_power(False)

        spins = random.randint(15, 25)
        delay = 50

        state = {"current": "ARAM"}

        def do_spin(count):
            if count > 0:
                state["current"] = random.choice(modes)
                next_delay = delay + int((spins - count) * 4)
                self.after(next_delay, lambda: do_spin(count - 1))
            else:
                winner = state["current"]
                self.config.set("queue_mode", winner)
                EventBus.emit("show_toast", f"Roulette landed on {winner}!", "🎰", 4000, "success", True)
                self.after(500, self._hotkey_find_match)

        do_spin(spins)

    def _restart_ux(self):
        Logger.info("SYS", "Restarting League UX...")
        def _execute():
            success = False
            if self.lcu and self.lcu.is_connected:
                res = self.lcu.request("POST", "/riotclient/kill-and-restart-ux")
                if res and res.status_code in [200, 204]:
                    success = True

            if not success:
                subprocess.run(["taskkill", "/IM", "LeagueClientUx.exe", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

            Logger.info("SYS", "UX Restart Triggered.")

        threading.Thread(target=_execute, daemon=True).start()
