"""
Login Automation Module
───────────────────────
Handles automated login/logout and credential entry for the Riot Client.
Extracted from AccountManager to keep that class focused on CRUD operations.
"""
import ctypes
import ctypes.wintypes
import os
import subprocess
import threading
import time
from typing import Callable, Optional

import psutil

from utils.logger import Logger


class LoginAutomation:
    """Orchestrates Riot Client login/logout via keyboard macros and the local API."""

    def __init__(self, riot_client, launch_client_func=None):
        self.riot_client = riot_client
        self._launch_client_func = launch_client_func
        self._login_in_progress = False

    # ─────────── Login Flow ───────────

    def login(self, username: str, password: str, label: str, idx: int,
              log_func: Optional[Callable] = None,
              completion_func: Optional[Callable] = None,
              on_success: Optional[Callable] = None):
        """Run the login automation on a background thread.

        Args:
            username: Riot login username.
            password: Decrypted password.
            label: Display label for logging.
            idx: Account index for tracking.
            log_func: Status callback.
            completion_func: Called with bool success.
            on_success: Called with (idx, label) on successful auth.
        """
        if self._login_in_progress:
            if log_func:
                log_func("Login already in progress...")
            return

        if not username or not password:
            if log_func:
                log_func("Account credentials incomplete.")
            return

        def _execute():
            self._login_in_progress = True
            try:
                if log_func:
                    log_func(f"Switching to {label}...")
                self._keyboard_login(username, password, label, log_func,
                                     completion_func, idx, on_success)
            except Exception as e:
                Logger.error("LoginAutomation", f"Login automation failed: {e}")
                if log_func:
                    log_func(f"Login failed: {e}")
                if completion_func:
                    completion_func(False)
            finally:
                self._login_in_progress = False

        threading.Thread(target=_execute, daemon=True).start()

    # ─────────── Sign Out ───────────

    def sign_out(self, log_func=None, completion_func=None,
                 on_success: Optional[Callable] = None):
        """Sign out of the current Riot account on a background thread."""
        def _execute():
            try:
                if log_func:
                    log_func("Signing out...")

                if not self.riot_client.is_riot_client_running():
                    if log_func:
                        log_func("Riot Client is not running.")
                    if completion_func:
                        completion_func(False)
                    return

                if log_func:
                    log_func("Closing League Client...")
                self.kill_game_processes(log_func)
                time.sleep(2)

                if not self.riot_client.is_connected:
                    self.riot_client.connect()

                if not self.riot_client.is_connected:
                    if log_func:
                        log_func("Cannot connect to Riot Client.")
                    if completion_func:
                        completion_func(False)
                    return

                success = self.riot_client.sign_out()

                if success:
                    if log_func:
                        log_func("Signed out successfully!")
                    if on_success:
                        on_success()
                else:
                    if log_func:
                        log_func("Sign out failed. Check the Riot Client.")

                if completion_func:
                    completion_func(success)

            except Exception as e:
                Logger.error("LoginAutomation", f"Sign out failed: {e}")
                if log_func:
                    log_func(f"Sign out error: {e}")
                if completion_func:
                    completion_func(False)

        threading.Thread(target=_execute, daemon=True).start()

    # ─────────── Keyboard Login ───────────

    def _keyboard_login(self, username, password, label, log_func,
                        completion_func, idx, on_success=None):
        """Type credentials into the Riot Client login form via pyautogui."""
        try:
            import pyautogui

            user32 = ctypes.windll.user32

            hwnd = self._find_riot_client_window(timeout=30)
            if not hwnd:
                if log_func:
                    log_func("Riot Client window not found.")
                if completion_func:
                    completion_func(False)
                return

            if log_func:
                log_func("Waiting for login form...")
            time.sleep(0.5)

            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)

            if log_func:
                log_func(f"Typing credentials for {label}...")

            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.write(username, interval=0.03)
            time.sleep(0.2)

            pyautogui.press('tab')
            time.sleep(0.2)

            pyautogui.write(password, interval=0.03)
            time.sleep(0.2)

            pyautogui.press('enter')

            if log_func:
                log_func("Waiting for authentication...")
            self._wait_for_auth_result(idx, label, log_func, completion_func,
                                       on_success, timeout=15)

        except Exception as e:
            Logger.error("LoginAutomation", f"Keyboard login failed: {e}")
            if log_func:
                log_func(f"Keyboard login failed: {e}")
            if completion_func:
                completion_func(False)

    # ─────────── Helpers ───────────

    @staticmethod
    def kill_game_processes(log_func=None):
        """Kill League Client processes (required before sign-out can work)."""
        killed_any = False
        for proc_name in ["LeagueClient.exe", "LeagueClientUx.exe"]:
            try:
                result = subprocess.run(
                    ["taskkill", "/IM", proc_name, "/F"],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if result.returncode == 0:
                    killed_any = True
                    if log_func:
                        log_func(f"Stopped {proc_name}")
            except Exception:
                pass
        return killed_any

    def kill_all_riot_processes(self, log_func=None):
        """Kill ALL Riot/League processes for a clean restart."""
        if log_func:
            log_func("Closing Riot Client...")

        for proc_name in ["LeagueClient.exe", "LeagueClientUx.exe",
                          "RiotClientUx.exe", "Riot Client.exe"]:
            try:
                subprocess.run(
                    ["taskkill", "/IM", proc_name, "/F"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                pass

        time.sleep(1)

        try:
            subprocess.run(
                ["taskkill", "/IM", "RiotClientServices.exe", "/F"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass

        time.sleep(2)

        _RC_LOCKFILE_PATHS = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "Riot Games", "Riot Client", "Config", "lockfile"),
        ]
        for lf_path in _RC_LOCKFILE_PATHS:
            try:
                if os.path.exists(lf_path):
                    os.remove(lf_path)
            except Exception:
                pass

    def _find_riot_client_window(self, timeout=30) -> int:
        """Find the VISIBLE Riot Client window handle."""
        user32 = ctypes.windll.user32
        deadline = time.time() + timeout

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
        )

        while time.time() < deadline:
            found_hwnd = []
            def callback(hwnd, extra):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if buff.value == "Riot Client":
                        found_hwnd.append(hwnd)
                        return False
                return True

            user32.EnumWindows(WNDENUMPROC(callback), 0)
            if found_hwnd:
                return found_hwnd[0]
            time.sleep(0.5)
        return 0

    @staticmethod
    def get_window_position(hwnd) -> tuple:
        """Return (x, y) of the window's top-left corner."""
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return rect.left, rect.top

    def _wait_for_auth_result(self, idx, label, log_func, completion_func,
                              on_success=None, timeout=15):
        """Poll the Riot Client API for authentication result after form submission."""
        deadline = time.time() + timeout
        self.riot_client.connect()

        while time.time() < deadline:
            time.sleep(0.5)
            session = self.riot_client.get_session()
            if session:
                err = session.get("error", "")
                if err:
                    if log_func:
                        log_func(f"Login fault: {err}")
                    if completion_func:
                        completion_func(False)
                    return
                if session.get("type", "") == "authenticated":
                    if log_func:
                        log_func(f"Logged in as {label}!")
                    if on_success:
                        on_success(idx, label)
                    if completion_func:
                        completion_func(True)
                    return

        if log_func:
            log_func("Login timed out. Check the Riot Client.")
        if completion_func:
            completion_func(False)

    def wait_for_riot_client_api(self, timeout=30) -> bool:
        """Poll until the Riot Client API is reachable."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.riot_client.connect():
                return True
            time.sleep(1)
        return False

    def wait_for_riot_client(self, timeout=30, log_func=None) -> bool:
        """Wait for the Riot Client process to start."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.riot_client.is_riot_client_running():
                time.sleep(2)
                return True
            time.sleep(0.5)
        return False

    def launch_riot_client(self):
        """Launch the Riot Client."""
        if self._launch_client_func:
            self._launch_client_func()
            return

        candidates = [
            r"C:\Riot Games\Riot Client\RiotClientServices.exe",
            r"D:\Riot Games\Riot Client\RiotClientServices.exe",
            r"E:\Riot Games\Riot Client\RiotClientServices.exe",
            os.path.join(
                os.environ.get("USERPROFILE", ""),
                r"Riot Games\Riot Client\RiotClientServices.exe",
            ),
        ]

        try:
            import winreg
            for hkey in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
                try:
                    key = winreg.OpenKey(
                        hkey,
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game league_of_legends.live"
                    )
                    val, _ = winreg.QueryValueEx(key, "UninstallString")
                    if val and "RiotClientServices.exe" in val:
                        path = val.split('"')[1] if '"' in val else val.split(' ')[0]
                        if os.path.exists(path):
                            candidates.insert(0, path)
                except Exception:
                    pass
        except Exception:
            pass

        for c in candidates:
            if os.path.exists(c):
                args = "--launch-product=league_of_legends --launch-patchline=live"
                try:
                    ctypes.windll.shell32.ShellExecuteW(
                        None, "open", c, args, None, 1
                    )
                except Exception:
                    subprocess.Popen(
                        [c] + args.split(),
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                return
