"""
Hotkey Manager Mixin
────────────────────
Extracted from main.py — handles global hotkey registration and all
hotkey-triggered actions (launch client, find match, toggle automation,
queue roulette, QR popup, restart UX, account switching).
"""
import os
import random
import subprocess
import threading

import ctypes
import keyboard  # type: ignore
import customtkinter as ctk  # type: ignore

from utils.logger import Logger
from ui.components.factory import get_font, get_color


class HotkeyManagerMixin:
    """Mixin providing hotkey registration and action handlers for LeagueLoopApp."""

    def _bind_hotkeys(self):
        try:
            keyboard.unhook_all()
        except Exception as e:
            Logger.debug("SYS", f"Failed to unhook hotkeys: {e}")

        self._launch_hotkey = self.config.get("hotkey_launch_client", "ctrl+shift+l")
        self._automation_hotkey = self.config.get("hotkey_toggle_automation", "ctrl+shift+a")
        self._queue_hotkey = self.config.get("hotkey_find_match", "ctrl+shift+f")
        self._mini_hotkey = self.config.get("hotkey_compact_mode", "ctrl+shift+m")

        try:
            keyboard.add_hotkey(self._launch_hotkey, self._hotkey_launch_client, suppress=False)
            keyboard.add_hotkey(self._automation_hotkey, self._hotkey_toggle_automation, suppress=False)
            keyboard.add_hotkey(self._queue_hotkey, self._hotkey_find_match, suppress=False)
            keyboard.add_hotkey(self._mini_hotkey, lambda: self.after(0, self.mini_player.toggle), suppress=False)
        except Exception as e:
            Logger.error("SYS", f"Failed to register hotkeys: {e}")

    def _hotkey_find_match(self):
        """Invokes the match finder via global hotkey registration."""
        self.state("normal")
        self.attributes("-topmost", True)
        self.after(0, self.sidebar._find_match)

    def _hotkey_toggle_automation(self):
        self.after(0, self.sidebar._on_power_click)

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
                    for hkey in [getattr(winreg, "HKEY_CURRENT_USER", 0), getattr(winreg, "HKEY_LOCAL_MACHINE", 0)]:
                        try:
                            key = getattr(winreg, "OpenKey")(hkey, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game league_of_legends.live")
                            val, _ = getattr(winreg, "QueryValueEx")(key, "UninstallString")
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
                    if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                        self.sidebar.update_action_log("Launching Riot Client...")
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
            if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                self.sidebar.update_action_log("Error: Could not find Riot Client.")
        self.after(0, _launch)

    def _switch_account_by_label(self, label):
        """Switch to an account identified by its label."""
        if not hasattr(self, "account_manager"):
            return
        for i, acct in enumerate(self.account_manager.get_accounts()):
            if acct.get("label", "") == label:
                def _log(msg):
                    if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
                        self.sidebar.update_action_log(msg)
                self.account_manager.login_account(i, log_func=_log)
                return

    def _show_mobile_qr(self):
        """Shows a popup with the QR code and IP to connect the mobile app."""
        from ui.components.toast import ToastManager
        if not self._local_ip:
            ToastManager.get_instance().show("API Server not running.", theme="error")
            return

        popup = ctk.CTkToplevel(self)
        popup.title("Link Mobile Device")
        popup.geometry("300x350")
        popup.attributes("-topmost", True)
        popup.resizable(False, False)

        lbl_info = ctk.CTkLabel(popup, text=f"Connect your phone to:", font=get_font("fonts.body"))
        lbl_info.pack(pady=(20, 5))

        lbl_ip = ctk.CTkLabel(popup, text=f"{self._local_ip}:{self._local_port}", font=get_font("fonts.title"), text_color=get_color("colors.accent.primary"))
        lbl_ip.pack(pady=5)

        qr_url = f"http://api.qrserver.com/v1/create-qr-code/?data=http://{self._local_ip}:{self._local_port}&size=200x200"

        import urllib.request
        from io import BytesIO
        from PIL import Image

        img_label = ctk.CTkLabel(popup, text="Loading QR Code...")
        img_label.pack(pady=10)

        def _fetch_qr():
            try:
                with urllib.request.urlopen(qr_url, timeout=5) as u:
                    raw_data = u.read()
                image = Image.open(BytesIO(raw_data))
                ctk_img = ctk.CTkImage(light_image=image, dark_image=image, size=(200, 200))
                self.after(0, lambda: img_label.configure(image=ctk_img, text=""))
            except Exception as e:
                self.after(0, lambda: img_label.configure(text=f"Failed to load QR.\nPlease connect manually via IP."))

        threading.Thread(target=_fetch_qr, daemon=True).start()

    def _quick_queue(self, mode_name):
        from ui.components.toast import ToastManager
        if not hasattr(self, "sidebar") or not self.sidebar.winfo_exists():
            return

        self.sidebar._on_mode_change(mode_name)
        self.after(50, self.sidebar._find_match)

        try:
            ToastManager.get_instance().show(
                f"Queued up for {mode_name}!",
                icon="🎮",
                duration=3000,
                theme="success"
            )
        except Exception as e:
            Logger.error("SYS", f"Toast error: {e}")

    def _queue_roulette(self):
        from ui.components.toast import ToastManager
        if not hasattr(self, "sidebar") or not self.sidebar.winfo_exists():
            return

        modes = [
            "Quickplay", "Draft Pick", "Ranked Solo/Duo", "Ranked Flex",
            "ARAM", "Arena", "Brawl", "TFT Normal"
        ]

        if getattr(self.sidebar, "power_state", False):
            self.sidebar._on_power_click()

        spins = random.randint(15, 25)
        delay = 50

        state = {"current": "ARAM"}

        def do_spin(count):
            if count > 0:
                state["current"] = random.choice(modes)
                if hasattr(self.sidebar, "queue_label"):
                    self.sidebar.queue_label.configure(text=state["current"])
                next_delay = delay + int((spins - count) * 4)
                self.after(next_delay, lambda: do_spin(count - 1))
            else:
                winner = state["current"]
                self.sidebar._on_mode_change(winner)

                try:
                    ToastManager.get_instance().show(
                        f"Roulette landed on {winner}!",
                        icon="🎰",
                        duration=4000,
                        theme="success",
                        confetti=True
                    )
                except Exception as e:
                    Logger.error("SYS", f"Toast error: {e}")

                self.after(500, self.sidebar._find_match)

        do_spin(spins)

    def _restart_ux(self):
        if hasattr(self, "sidebar") and self.sidebar.winfo_exists():
            self.sidebar.update_action_log("Restarting League UX...")

        def _execute():
            success = False
            if self.lcu and self.lcu.is_connected:
                res = self.lcu.request("POST", "/riotclient/kill-and-restart-ux")
                if res and res.status_code in [200, 204]:
                    success = True

            if not success:
                subprocess.run(["taskkill", "/IM", "LeagueClientUx.exe", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

            self.after(0, lambda: self.sidebar.update_action_log("UX Restart Triggered."))

        threading.Thread(target=_execute, daemon=True).start()
