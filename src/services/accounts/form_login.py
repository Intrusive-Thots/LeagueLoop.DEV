"""
RiotFormFiller - type a stored username and password into the Riot Client's
sign-in form and submit it.

Why this exists
---------------
Riot's local credential endpoint is guarded by hCaptcha, so a password cannot
be POSTed to the client. Restoring copied session files does not work either:
without "Stay signed in" the client keeps no reusable session. What does work
is what a person does: sign out, then type into the form on screen. This
module does exactly that, carefully:

* **The right window.** Only a visible top-level window titled "Riot Client"
  owned by the Riot Client's own process is used.
* **Focus is proven, not assumed.** The window is brought to the front and
  every single character is sent only after re-checking that the Riot Client
  is still the foreground window. If anything steals focus mid-way, typing
  stops at once (at most nothing more is typed anywhere else), the fields are
  cleared and the attempt is retried.
* **Layout independent input.** Characters are sent as Unicode key events
  (KEYEVENTF_UNICODE), so keyboard layout, Caps Lock and held Shift do not
  change what is typed.
* **Field targeting.** With UI Automation available (pywinauto installed) the
  USERNAME and PASSWORD boxes are focused by name. Without it, the client's
  own autofocus on USERNAME is used, then Tab to PASSWORD - and a retry
  returns to USERNAME with Shift+Tab first if it was interrupted in PASSWORD.
* **The password is never logged**, never put on the clipboard, never put in
  a progress message or an exception detail.

Everything OS-specific sits behind `Desktop`, so the sequencing is tested
with a fake on any platform.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, List, Optional

from utils.logger import Logger

TAG = "RiotFormLogin"

#: Window title of the Riot Client UI (Chromium/Electron).
RIOT_WINDOW_TITLE = "Riot Client"
#: Process names that may own that window.
RIOT_UI_PROCESSES = ("riot client.exe", "riotclientux.exe")

DEFAULT_ATTEMPTS = 3
DEFAULT_WINDOW_TIMEOUT_S = 30.0
#: After the sign-in screen appears it animates in; keys sent during that are
#: dropped. This is the pause before the first key.
DEFAULT_FORM_SETTLE_S = 2.0
#: Pause between characters. Chromium is fine with fast input but a small gap
#: keeps React-controlled inputs from coalescing events.
DEFAULT_KEY_INTERVAL_S = 0.012
DEFAULT_STEP_PAUSE_S = 0.15


class FillStatus(Enum):
    SUBMITTED = "submitted"
    #: No Riot Client window appeared.
    WINDOW_NOT_FOUND = "window_not_found"
    #: The window could not be brought to the front.
    FOCUS_FAILED = "focus_failed"
    #: Something kept taking focus away while typing, on every attempt.
    FOCUS_LOST = "focus_lost"
    #: This machine cannot send input (not Windows).
    UNAVAILABLE = "unavailable"


@dataclass
class FormFields:
    """Handles for the two inputs, when UI Automation can see them."""

    username: Any
    password: Any


@dataclass(frozen=True)
class FillResult:
    status: FillStatus
    attempts: int = 0
    detail: str = ""
    #: True when UI Automation located the fields; False means autofocus+Tab.
    targeted: bool = False

    @property
    def ok(self) -> bool:
        return self.status is FillStatus.SUBMITTED


class Desktop:
    """What the filler needs from the OS. Implemented for Windows below."""

    def available(self) -> bool:  # pragma: no cover - interface
        return False

    def find_riot_window(self) -> int:  # pragma: no cover - interface
        return 0

    def bring_to_front(self, hwnd: int) -> bool:  # pragma: no cover
        return False

    def is_foreground(self, hwnd: int) -> bool:  # pragma: no cover
        return False

    def release_modifiers(self) -> None:  # pragma: no cover
        pass

    def press(self, key: str) -> None:  # pragma: no cover
        """key in: tab, shift+tab, enter, backspace, ctrl+a."""

    def type_char(self, ch: str) -> None:  # pragma: no cover
        pass

    def find_fields(self, hwnd: int) -> Optional[FormFields]:  # pragma: no cover
        return None

    def focus_field(self, field: Any) -> bool:  # pragma: no cover
        return False

    def captcha_visible(self, hwnd: int) -> Optional[bool]:  # pragma: no cover
        """True/False when UI Automation can tell, None when it cannot."""
        return None


class _FocusLost(Exception):
    pass


class RiotFormFiller:
    """Fills and submits the Riot sign-in form. Blocking; run off the UI thread."""

    def __init__(
        self,
        desktop: Optional[Desktop] = None,
        attempts: int = DEFAULT_ATTEMPTS,
        window_timeout_s: float = DEFAULT_WINDOW_TIMEOUT_S,
        form_settle_s: float = DEFAULT_FORM_SETTLE_S,
        key_interval_s: float = DEFAULT_KEY_INTERVAL_S,
        step_pause_s: float = DEFAULT_STEP_PAUSE_S,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.monotonic,
    ):
        self.desktop = desktop if desktop is not None else default_desktop()
        self.attempts = max(1, int(attempts))
        self.window_timeout_s = window_timeout_s
        self.form_settle_s = form_settle_s
        self.key_interval_s = key_interval_s
        self.step_pause_s = step_pause_s
        self._sleep = sleep
        self._now = now

    # ------------------------------------------------------------ queries
    def available(self) -> bool:
        try:
            return bool(self.desktop.available())
        except Exception:
            return False

    def wait_for_window(self, timeout_s: Optional[float] = None) -> int:
        """Handle of the Riot Client window, waiting up to `timeout_s`."""
        timeout = self.window_timeout_s if timeout_s is None else timeout_s
        deadline = self._now() + max(0.0, timeout)
        while True:
            try:
                hwnd = self.desktop.find_riot_window()
            except Exception as exc:
                Logger.debug(TAG, "Window lookup failed", exc=exc)
                hwnd = 0
            if hwnd:
                return hwnd
            if self._now() >= deadline:
                return 0
            self._sleep(0.5)

    def form_ready(self, hwnd: int) -> Optional[bool]:
        """Can UI Automation see both inputs? None when it cannot look."""
        try:
            fields = self.desktop.find_fields(hwnd)
        except Exception:
            return None
        if fields is None:
            return None
        return bool(fields.username is not None and fields.password is not None)

    def captcha_visible(self) -> Optional[bool]:
        try:
            hwnd = self.desktop.find_riot_window()
            if not hwnd:
                return None
            return self.desktop.captcha_visible(hwnd)
        except Exception:
            return None

    # ------------------------------------------------------------- action
    def fill_and_submit(
        self,
        username: str,
        password: str,
        on_step: Optional[Callable[[str], None]] = None,
    ) -> FillResult:
        """Type both fields and press Enter. Never raises; never logs secrets."""
        step = on_step or (lambda _msg: None)
        if not self.available():
            return FillResult(FillStatus.UNAVAILABLE, 0, "Typing into the Riot Client needs Windows.")

        last = FillStatus.FOCUS_FAILED
        #: Which input focus was in when an attempt was interrupted, so a
        #: keyboard-only retry can walk back to USERNAME.
        in_password = False
        for attempt in range(1, self.attempts + 1):
            hwnd = self.wait_for_window()
            if not hwnd:
                return FillResult(FillStatus.WINDOW_NOT_FOUND, attempt)

            if attempt > 1:
                step(
                    "Retrying - attempt {} of {}. Please don't click other "
                    "windows while LeagueLoop types.".format(attempt, self.attempts)
                )
            try:
                fronted = bool(self.desktop.bring_to_front(hwnd))
            except Exception:
                fronted = False
            if not fronted or not self._is_front(hwnd):
                last = FillStatus.FOCUS_FAILED
                Logger.warning(TAG, f"Could not bring the Riot Client to the front (attempt {attempt})")
                self._sleep(1.0)
                continue

            self._sleep(self.form_settle_s if attempt == 1 else self.step_pause_s * 4)
            try:
                fields = self.desktop.find_fields(hwnd)
            except Exception:
                fields = None
            targeted = bool(fields and fields.username is not None and fields.password is not None)

            try:
                self._safe_release()
                # ---- USERNAME
                if targeted:
                    if not self.desktop.focus_field(fields.username):
                        raise _FocusLost()
                elif in_password:
                    self._key(hwnd, "shift+tab")
                in_password = False
                self._clear_and_type(hwnd, username)

                # ---- PASSWORD
                if targeted:
                    if not self.desktop.focus_field(fields.password):
                        raise _FocusLost()
                else:
                    self._key(hwnd, "tab")
                in_password = True
                self._clear_and_type(hwnd, password)

                # ---- SUBMIT (Enter in PASSWORD = the arrow button)
                self._key(hwnd, "enter")
                in_password = True
                Logger.info(
                    TAG,
                    f"Sign-in form submitted (attempt {attempt}, "
                    f"{'fields located' if targeted else 'autofocus + Tab'})",
                )
                return FillResult(FillStatus.SUBMITTED, attempt, targeted=targeted)
            except _FocusLost:
                last = FillStatus.FOCUS_LOST
                Logger.warning(
                    TAG,
                    f"The Riot Client lost focus while typing (attempt {attempt}); "
                    f"stopped typing and will retry",
                )
                self._sleep(1.0)
                continue
            except Exception as exc:
                # Type name only: an exception message is never echoed, in
                # case it ever contained typed text.
                last = FillStatus.FOCUS_LOST
                Logger.warning(TAG, f"Typing failed ({type(exc).__name__}); will retry")
                self._sleep(1.0)
                continue
        return FillResult(last, self.attempts)

    # ------------------------------------------------------------ helpers
    def _is_front(self, hwnd: int) -> bool:
        try:
            return bool(self.desktop.is_foreground(hwnd))
        except Exception:
            return False

    def _safe_release(self) -> None:
        try:
            self.desktop.release_modifiers()
        except Exception as exc:
            Logger.debug(TAG, "Could not release modifier keys", exc=exc)

    def _key(self, hwnd: int, key: str) -> None:
        if not self._is_front(hwnd):
            raise _FocusLost()
        self.desktop.press(key)
        self._sleep(self.step_pause_s)

    def _clear_and_type(self, hwnd: int, text: str) -> None:
        self._key(hwnd, "ctrl+a")
        self._key(hwnd, "backspace")
        for ch in text:
            # Checked before *every* character: the moment the Riot Client is
            # not in front, nothing more is typed.
            if not self._is_front(hwnd):
                raise _FocusLost()
            self.desktop.type_char(ch)
            if self.key_interval_s:
                self._sleep(self.key_interval_s)
        self._sleep(self.step_pause_s)


# =====================================================================
# Windows implementation
# =====================================================================
class Win32Desktop(Desktop):
    """SendInput + EnumWindows via ctypes; optional pywinauto UIA."""

    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004
    INPUT_KEYBOARD = 1
    VK = {"tab": 0x09, "enter": 0x0D, "backspace": 0x08, "shift": 0x10,
          "ctrl": 0x11, "alt": 0x12, "a": 0x41}

    def __init__(self):
        self._ok = sys.platform == "win32"
        self._uia_checked = False
        self._uia = None
        if self._ok:
            try:
                self._setup()
            except Exception as exc:
                Logger.warning(TAG, f"Input automation unavailable: {exc}")
                self._ok = False

    def _setup(self) -> None:
        import ctypes
        from ctypes import wintypes

        self.ct = ctypes
        self.wt = wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        ULONG_PTR = ctypes.c_size_t

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ULONG_PTR)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                        ("wParamH", wintypes.WORD)]

        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        self.KEYBDINPUT, self.INPUT = KEYBDINPUT, INPUT
        self.user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self.user32.SendInput.restype = wintypes.UINT
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetAncestor.restype = wintypes.HWND
        self.user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        self.WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def available(self) -> bool:
        return self._ok

    # ---- windows
    def _pid_name(self, hwnd) -> str:
        pid = self.wt.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, self.ct.byref(pid))
        try:
            import psutil
            return psutil.Process(pid.value).name().lower()
        except Exception:
            return ""

    def find_riot_window(self) -> int:
        found: List[tuple] = []

        def cb(hwnd, _lp):
            try:
                if not self.user32.IsWindowVisible(hwnd):
                    return True
                n = self.user32.GetWindowTextLengthW(hwnd)
                if n <= 0:
                    return True
                buf = self.ct.create_unicode_buffer(n + 1)
                self.user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value != RIOT_WINDOW_TITLE:
                    return True
                if self._pid_name(hwnd) not in RIOT_UI_PROCESSES:
                    return True
                rect = self.wt.RECT()
                self.user32.GetWindowRect(hwnd, self.ct.byref(rect))
                area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
                found.append((area, int(hwnd)))
            except Exception as exc:
                Logger.debug(TAG, "Skipped a window during lookup", exc=exc)
            return True

        self.user32.EnumWindows(self.WNDENUMPROC(cb), 0)
        if not found:
            return 0
        found.sort(reverse=True)
        return found[0][1]

    def is_foreground(self, hwnd: int) -> bool:
        fg = self.user32.GetForegroundWindow()
        if not fg:
            return False
        root = self.user32.GetAncestor(fg, 2)  # GA_ROOT
        return int(root or fg) == int(hwnd)

    def bring_to_front(self, hwnd: int) -> bool:
        u = self.user32
        if u.IsIconic(hwnd):
            u.ShowWindow(hwnd, 9)  # SW_RESTORE
        else:
            u.ShowWindow(hwnd, 5)  # SW_SHOW
        if u.SetForegroundWindow(hwnd) and self._settled_front(hwnd):
            return True
        # Windows refuses foreground changes from a process that is not in
        # front. Attaching to the foreground thread's input queue is the
        # documented way round it while LeagueLoop still has the user's click.
        fg = u.GetForegroundWindow()
        cur = self.kernel32.GetCurrentThreadId()
        other = u.GetWindowThreadProcessId(fg, None) if fg else 0
        attached = False
        try:
            if other and other != cur:
                attached = bool(u.AttachThreadInput(other, cur, True))
            u.BringWindowToTop(hwnd)
            u.SetForegroundWindow(hwnd)
        finally:
            if attached:
                u.AttachThreadInput(other, cur, False)
        return self._settled_front(hwnd)

    def _settled_front(self, hwnd: int) -> bool:
        for _ in range(10):
            if self.is_foreground(hwnd):
                return True
            time.sleep(0.05)
        return False

    # ---- keys
    def _send(self, *events) -> None:
        arr = (self.INPUT * len(events))()
        for i, (vk, scan, flags) in enumerate(events):
            arr[i].type = self.INPUT_KEYBOARD
            arr[i].ki = self.KEYBDINPUT(vk, scan, flags, 0, 0)
        sent = self.user32.SendInput(len(events), arr, self.ct.sizeof(self.INPUT))
        if sent != len(events):
            raise OSError("SendInput was blocked")

    def release_modifiers(self) -> None:
        for name in ("shift", "ctrl", "alt"):
            vk = self.VK[name]
            if self.user32.GetAsyncKeyState(vk) & 0x8000:
                self._send((vk, 0, self.KEYEVENTF_KEYUP))

    def press(self, key: str) -> None:
        up = self.KEYEVENTF_KEYUP
        if key == "ctrl+a":
            c, a = self.VK["ctrl"], self.VK["a"]
            self._send((c, 0, 0), (a, 0, 0), (a, 0, up), (c, 0, up))
        elif key == "shift+tab":
            s, t = self.VK["shift"], self.VK["tab"]
            self._send((s, 0, 0), (t, 0, 0), (t, 0, up), (s, 0, up))
        else:
            vk = self.VK[key]
            self._send((vk, 0, 0), (vk, 0, up))

    def type_char(self, ch: str) -> None:
        data = ch.encode("utf-16-le")
        units = [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]
        events = []
        for unit in units:
            events.append((0, unit, self.KEYEVENTF_UNICODE))
            events.append((0, unit, self.KEYEVENTF_UNICODE | self.KEYEVENTF_KEYUP))
        self._send(*events)

    # ---- optional UI Automation (pywinauto)
    def _uia_window(self, hwnd: int):
        if not self._uia_checked:
            self._uia_checked = True
            try:
                from pywinauto import Desktop as _UiaDesktop  # type: ignore
                self._uia = _UiaDesktop(backend="uia")
            except Exception:
                self._uia = None
                Logger.info(
                    TAG,
                    "pywinauto is not installed; using the Riot Client's "
                    "autofocus and Tab to reach the fields",
                )
        if self._uia is None:
            return None
        try:
            return self._uia.window(handle=hwnd)
        except Exception:
            return None

    @staticmethod
    def _name(el) -> str:
        try:
            info = el.element_info
            return " ".join(
                str(x or "") for x in (info.name, getattr(info, "automation_id", ""))
            ).lower()
        except Exception:
            return ""

    def find_fields(self, hwnd: int) -> Optional[FormFields]:
        win = self._uia_window(hwnd)
        if win is None:
            return None
        try:
            edits = win.descendants(control_type="Edit")
        except Exception:
            return None
        user = pw = None
        for el in edits:
            name = self._name(el)
            if pw is None and "password" in name:
                pw = el
            elif user is None and ("username" in name or "user name" in name):
                user = el
        if user is None or pw is None:
            # The Riot Client (Chromium) usually exposes only empty panes to
            # UI Automation. Seeing no fields means "can't look", not "the
            # form isn't there" - fall back to autofocus + Tab.
            return None
        return FormFields(user, pw)

    def focus_field(self, field: Any) -> bool:
        try:
            field.set_focus()
            return True
        except Exception:
            return False

    def captcha_visible(self, hwnd: int) -> Optional[bool]:
        win = self._uia_window(hwnd)
        if win is None:
            return None
        try:
            saw_content = False
            for el in win.descendants():
                name = self._name(el)
                if "captcha" in name:
                    return True
                saw_content = saw_content or bool(name.strip())
            # Only empty panes: UI Automation can't see the page, so it
            # can't rule a captcha out either.
            return False if saw_content else None
        except Exception:
            return None


def default_desktop() -> Desktop:
    return Win32Desktop() if sys.platform == "win32" else Desktop()
