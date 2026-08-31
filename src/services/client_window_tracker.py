"""
Where the League Client's window is.

The application already knew *whether* the client was running — `ClientDetector`
reads the lockfile and the process list and reports `{port, token, connected,
pid}`. Nothing anywhere knew where its window sat on screen, which is why the
companion panel could only ever float wherever it was last dragged.

This service answers that one question and publishes it as
`ClientWindowState`. Widgets read it from application state; no widget calls
Win32 itself.

Discovery, then tracking
------------------------
Enumerating every top-level window is not something to do ten times a second,
so the two jobs are separated::

    PID known?  ── no ──▶  wait for ClientDetector
        │
       yes
        ▼
    discover HWND   (enumerate once, validate candidates)
        │
        ▼
    track HWND      (cheap per-tick reads: rect, visible, minimised)
        │
    handle dies ──▶ re-discover

Once a handle is found the per-tick cost is three Win32 calls against a known
HWND. Enumeration only happens again if that handle stops being valid.

Picking the right window
------------------------
`LeagueClientUx.exe` owns several windows: the real UX window, hidden helper
windows, and Chromium's message-only children. Taking the first one found is
wrong. `_score_candidate` rejects anything that is not a visible, top-level,
non-zero-sized window owned by the client's PID, and prefers the largest
remaining candidate — the actual client is by a wide margin the biggest
window the process owns.

Testability
-----------
All platform access goes through `WindowBackend`. `Win32WindowBackend` is the
real one; tests inject a fake. Nothing in this module imports `win32gui` at
module scope, so it loads and is testable on any platform — which matters,
because this repository is developed on Linux and League only runs on Windows.
"""
from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol, Tuple

from core.state import ClientWindowState
from utils.logger import Logger

TAG = "ClientWindow"

#: Executables that own a League *client* window. The game itself is not one
#: of them: this is a client companion and must never attach to the game.
CLIENT_EXECUTABLES = ("leagueclientux.exe", "leagueclient.exe", "riotclientux.exe")

#: A window smaller than this in either axis is a helper, not the client.
MIN_CLIENT_WIDTH = 400
MIN_CLIENT_HEIGHT = 300

#: How often to re-read a known handle. Geometry changes while a window is
#: being dragged, so this is faster than the 1s lifecycle poll — but it is
#: three cheap calls, not an enumeration.
DEFAULT_TRACK_INTERVAL_S = 0.20
#: How often to look for the window when we do not have a handle yet.
DEFAULT_DISCOVERY_INTERVAL_S = 2.0


@dataclass(frozen=True)
class WindowInfo:
    """One candidate window, as reported by the platform."""

    hwnd: int
    pid: int
    title: str
    rect: Tuple[int, int, int, int]  # x, y, width, height
    visible: bool
    minimized: bool
    is_toplevel: bool = True
    #: HMONITOR of the display the window is mostly on. 0 when unknown.
    monitor: int = 0
    #: Effective DPI of that display. 96 = 100%. 0 when unknown.
    dpi: int = 0


class WindowBackend(Protocol):
    """The platform calls this service needs. Implemented for Win32; faked
    in tests."""

    def enumerate_windows(self) -> List[WindowInfo]:
        """Every top-level window currently on the desktop."""

    def get_window(self, hwnd: int) -> Optional[WindowInfo]:
        """One window by handle, or None if the handle is no longer valid."""


class Win32WindowBackend:
    """The real thing. Imports Win32 lazily so this module stays portable."""

    def __init__(self) -> None:
        self._win32gui = None
        self._win32process = None
        self._win32con = None
        self._available: Optional[bool] = None

    def available(self) -> bool:
        if self._available is not None:
            return self._available
        if sys.platform != "win32":
            self._available = False
            return False
        try:
            import win32con
            import win32gui
            import win32process

            self._win32gui = win32gui
            self._win32process = win32process
            self._win32con = win32con
            self._available = True
        except Exception as exc:
            Logger.warning(
                TAG,
                "pywin32 is not available, so the League Client window cannot "
                "be tracked. The companion panel will not attach to it.",
                exc=exc,
            )
            self._available = False
        return self._available

    # -------------------------------------------------------- monitor + dpi
    def _monitor_and_dpi(self, hwnd: int) -> Tuple[int, int]:
        """(HMONITOR, effective DPI) for a window. Zeros when unavailable.

        Read through ctypes rather than pywin32 because the per-monitor DPI
        entry points live in different DLLs across Windows versions and
        pywin32 does not wrap all of them:

        * ``GetDpiForWindow``  - Windows 10 1607+, the correct answer
        * ``GetDpiForMonitor`` - Windows 8.1+, shcore, effective DPI
        * 96                   - anything older, i.e. no scaling awareness

        The monitor handle is what tells us the window *moved to another
        display*, which a rect change alone cannot: dragging a window to an
        identically-positioned region of a second monitor changes the DPI but
        not necessarily the coordinates in a way we could interpret.
        """
        try:
            import ctypes

            user32 = ctypes.windll.user32
            # MONITOR_DEFAULTTONEAREST: never return NULL for an off-screen
            # window; the nearest display is the useful answer.
            monitor = int(user32.MonitorFromWindow(ctypes.c_void_p(hwnd), 2) or 0)
        except Exception:
            return (0, 0)

        dpi = 0
        try:
            dpi = int(user32.GetDpiForWindow(ctypes.c_void_p(hwnd)) or 0)
        except Exception:
            dpi = 0
        if not dpi and monitor:
            try:
                shcore = ctypes.windll.shcore
                dpi_x = ctypes.c_uint()
                dpi_y = ctypes.c_uint()
                # 0 = MDT_EFFECTIVE_DPI, the one that matches what the user
                # set in Display settings.
                if shcore.GetDpiForMonitor(
                    ctypes.c_void_p(monitor), 0,
                    ctypes.byref(dpi_x), ctypes.byref(dpi_y),
                ) == 0:
                    dpi = int(dpi_x.value)
            except Exception:
                dpi = 0
        return (monitor, dpi or 96)

    def _info(self, hwnd: int) -> Optional[WindowInfo]:
        gui, process = self._win32gui, self._win32process
        try:
            left, top, right, bottom = gui.GetWindowRect(hwnd)
            placement = gui.GetWindowPlacement(hwnd)
            minimized = placement[1] == self._win32con.SW_SHOWMINIMIZED
            _thread_id, pid = process.GetWindowThreadProcessId(hwnd)
            monitor, dpi = self._monitor_and_dpi(hwnd)
            return WindowInfo(
                hwnd=int(hwnd),
                pid=int(pid or 0),
                title=gui.GetWindowText(hwnd) or "",
                rect=(left, top, max(0, right - left), max(0, bottom - top)),
                visible=bool(gui.IsWindowVisible(hwnd)),
                minimized=bool(minimized),
                is_toplevel=gui.GetParent(hwnd) == 0,
                monitor=monitor,
                dpi=dpi,
            )
        except Exception:
            # A handle can go invalid between the check and the read. That is
            # ordinary, and the caller re-discovers.
            return None

    def enumerate_windows(self) -> List[WindowInfo]:
        if not self.available():
            return []
        found: List[WindowInfo] = []

        def _collect(hwnd, _extra):
            info = self._info(hwnd)
            if info is not None:
                found.append(info)
            return True

        try:
            self._win32gui.EnumWindows(_collect, None)
        except Exception as exc:
            Logger.error(TAG, "Enumerating windows failed.", exc=exc)
            return []
        return found

    def get_window(self, hwnd: int) -> Optional[WindowInfo]:
        if not self.available() or not hwnd:
            return None
        try:
            if not self._win32gui.IsWindow(hwnd):
                return None
        except Exception:
            return None
        return self._info(hwnd)


def _process_name(pid: int) -> str:
    """The executable name for a pid, or "" if it cannot be read."""
    if not pid:
        return ""
    try:
        import psutil

        return psutil.Process(pid).name().lower()
    except Exception:
        return ""


class ClientWindowTracker:
    """Finds the League Client window and keeps its geometry in state.

    Owns no UI and no process detection. It consumes the pid that
    `ClientDetector` already found, and publishes `ClientWindowState`.
    """

    def __init__(
        self,
        state_manager=None,
        pid_provider: Optional[Callable[[], Optional[int]]] = None,
        backend: Optional[WindowBackend] = None,
        track_interval_s: float = DEFAULT_TRACK_INTERVAL_S,
        discovery_interval_s: float = DEFAULT_DISCOVERY_INTERVAL_S,
    ) -> None:
        self._state = state_manager
        self._pid_provider = pid_provider or _default_pid_provider
        self._backend: WindowBackend = backend or Win32WindowBackend()
        self._track_interval_s = track_interval_s
        self._discovery_interval_s = discovery_interval_s

        self._hwnd: int = 0
        self._last_published: Optional[Tuple] = None
        self._last_discovery_at: float = 0.0
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        #: Extra listeners, for callers not going through StateManager.
        self._listeners: List[Callable[[ClientWindowState], None]] = []

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="ClientWindowTracker", daemon=True
        )
        self._thread.start()
        Logger.info(TAG, "Window tracker started.")

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        Logger.info(TAG, "Window tracker stopped.")

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def subscribe(self, callback: Callable[[ClientWindowState], None]) -> None:
        """Be told when the window's geometry changes."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:
                Logger.error(TAG, "Window tracking tick failed.", exc=exc)
            self._stop.wait(self._track_interval_s)

    # ---------------------------------------------------------------- work
    def tick(self) -> ClientWindowState:
        """One cycle. Returns the state it published (or the unchanged one)."""
        info = self._backend.get_window(self._hwnd) if self._hwnd else None

        if info is None or not self._still_ours(info):
            # The handle we had is gone or no longer belongs to the client.
            if self._hwnd:
                Logger.info(TAG, "Lost the client window; re-discovering.")
                self._hwnd = 0
            info = self._discover()

        if info is None:
            return self._publish(ClientWindowState())

        self._hwnd = info.hwnd
        x, y, width, height = info.rect
        return self._publish(ClientWindowState(
            found=True,
            hwnd=info.hwnd,
            x=x, y=y, width=width, height=height,
            visible=info.visible,
            minimized=info.minimized,
            monitor=info.monitor,
            dpi=info.dpi,
        ))

    def _still_ours(self, info: WindowInfo) -> bool:
        """A handle can be recycled by another process. Re-check ownership."""
        pid = self._pid_provider()
        if pid and info.pid and info.pid != pid:
            return False
        return True

    def _discover(self) -> Optional[WindowInfo]:
        """Enumerate and pick the client's real window.

        Rate-limited: enumeration is the expensive call, and while the client
        is closed there is nothing to find, so hammering it every 200 ms would
        be pure waste.
        """
        now = time.monotonic()
        if now - self._last_discovery_at < self._discovery_interval_s:
            return None
        self._last_discovery_at = now

        pid = self._pid_provider()
        candidates = [
            info for info in self._backend.enumerate_windows()
            if self._score_candidate(info, pid) > 0
        ]
        if not candidates:
            return None

        # The client is by far the largest window its process owns; the rest
        # are helpers and Chromium children.
        best = max(candidates, key=lambda i: self._score_candidate(i, pid))
        Logger.info(
            TAG,
            "Found the League Client window: {}x{} at ({}, {}) - {}".format(
                best.rect[2], best.rect[3], best.rect[0], best.rect[1],
                best.title or "untitled",
            ),
            hwnd=best.hwnd, pid=best.pid,
        )
        return best

    def _score_candidate(self, info: WindowInfo, pid: Optional[int]) -> int:
        """How likely this window is to be the client's. 0 means "not it"."""
        if not info.is_toplevel or not info.visible:
            return 0
        width, height = info.rect[2], info.rect[3]
        if width < MIN_CLIENT_WIDTH or height < MIN_CLIENT_HEIGHT:
            return 0

        info_proc = _process_name(info.pid)
        if pid:
            if info.pid != pid:
                pid_proc = _process_name(pid)
                if not (info_proc in CLIENT_EXECUTABLES and pid_proc in CLIENT_EXECUTABLES):
                    return 0
        else:
            if info_proc not in CLIENT_EXECUTABLES:
                if "league of legends" not in (info.title or "").lower():
                    return 0

        # Among the survivors, biggest wins.
        return width * height

    # ------------------------------------------------------------- publish
    def _publish(self, state: ClientWindowState) -> ClientWindowState:
        """Push to state and listeners, but only when something changed.

        Without this the tracker would emit identical geometry several times
        a second and every bound view would re-render for nothing.
        """
        key = state.geometry_key
        if key == self._last_published:
            return state
        previous = self._last_published
        self._last_published = key

        if self._state is not None:
            try:
                self._state.update_client_window(
                    found=state.found, hwnd=state.hwnd,
                    x=state.x, y=state.y,
                    width=state.width, height=state.height,
                    visible=state.visible, minimized=state.minimized,
                    monitor=state.monitor, dpi=state.dpi,
                )
            except Exception as exc:
                Logger.error(TAG, "Could not publish window state.", exc=exc)

        for listener in list(self._listeners):
            try:
                listener(state)
            except Exception as exc:
                Logger.error(TAG, "A window-state listener failed.", exc=exc)

        self._log_transition(previous, state)
        return state

    @staticmethod
    def _log_transition(previous: Optional[Tuple], state: ClientWindowState) -> None:
        """Say what changed, at a level that will not flood the log.

        Moves and resizes happen continuously while a window is dragged, so
        they are DEBUG. Appearing, vanishing and minimising are the events
        worth reading later.
        """
        if previous is None:
            return
        (was_found, _hwnd, _x, _y, _w, _h, _vis, was_min,
         was_monitor, was_dpi) = previous
        if was_found != state.found:
            Logger.info(
                TAG,
                "League Client window " + ("appeared." if state.found else "closed."),
            )
        elif was_min != state.minimized:
            Logger.info(
                TAG,
                "League Client " + ("minimised." if state.minimized else "restored."),
            )
        elif state.found and was_monitor and was_monitor != state.monitor:
            # Worth INFO: this is the case where the panel has to re-resolve
            # which screen's work area it is being clamped into.
            Logger.info(
                TAG,
                "League Client moved to another display "
                f"(DPI {was_dpi or 96} -> {state.dpi or 96}).",
                monitor=state.monitor,
            )
        elif state.found and was_dpi and was_dpi != state.dpi:
            Logger.info(
                TAG, f"Display scaling changed: {was_dpi} -> {state.dpi} DPI.",
            )
        else:
            Logger.debug(
                TAG, f"Client window geometry: {state.rect}",
            )


def _default_pid_provider() -> Optional[int]:
    """The client pid, from the detector that already found it.

    Deliberately not a second process scan: `scan_clients` caches, and
    duplicating it would mean two pieces of code disagreeing about whether
    the client is running.
    """
    try:
        from utils.client_detector import scan_clients

        return (scan_clients().get("league") or {}).get("pid")
    except Exception as exc:
        Logger.debug(TAG, "Could not read the client pid", exc=exc)
        return None
