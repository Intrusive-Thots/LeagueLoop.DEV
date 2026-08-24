"""
Run slow work off the GUI thread.

Several screens called straight into services that talk to the League Client
— the loot open does key forging, up to four passes, a `GET` per stack per
pass and N craft `POST`s with `time.sleep` between them; the profile does
three blocking `GET`s from `__init__`, `showEvent` *and* the connection
signal. All of it ran on the GUI thread, so the window was frozen and
unpaintable for the duration and the "Refreshing…" status the code carefully
set never actually rendered.

Usage::

    self._task = run_in_background(
        self.loot.summarize_openable,
        on_done=self._render_rows,
        on_error=self._report_failure,
        owner=self,
    )

`on_done` and `on_error` run on the GUI thread, so they may touch widgets.
Pass `owner` and the callbacks are dropped if the widget is destroyed before
the work finishes — otherwise a slow call outliving its screen reaches into
deleted C++ objects.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from utils.logger import Logger


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(object)


class BackgroundTask(QRunnable):
    """One call, run on the thread pool, answered on the GUI thread."""

    def __init__(self, fn: Callable[[], Any], label: str = "", owner=None):
        super().__init__()
        self._fn = fn
        self._label = label or getattr(fn, "__name__", "task")
        # Parented to the owner when there is one. This is the load-bearing
        # part: when the owner is destroyed Qt destroys the signal carrier
        # with it and drops every queued emit, so a result that arrives during
        # teardown is never delivered into half-deleted widgets. A Python-side
        # `alive` flag cannot do this on its own — the flag is checked inside
        # the slot, which by then is already running against dead C++ objects.
        self.signals = _Signals(owner)
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:  # noqa: D102 (QRunnable override)
        try:
            result = self._fn()
        except Exception as exc:
            Logger.error("Background", f"{self._label} failed.", exc=exc)
            try:
                self.signals.failed.emit(exc)
            except RuntimeError:
                # The receiver went away while we were working. Not an error.
                pass
            return
        try:
            self.signals.done.emit(result)
        except RuntimeError:
            # The receiver was destroyed while we were working. Ordinary at
            # shutdown, and not something the user needs told about.
            pass


def _deliver(callback: Callable[[Any], None], value: Any, label: str) -> None:
    """Call a GUI-thread callback, tolerating a screen that has gone away.

    `RuntimeError: Internal C++ object already deleted` is what PySide6 raises
    when a callback touches a widget Qt has destroyed. It is not a defect in
    the callback — the screen was torn down while the work was in flight — so
    it is a DEBUG line, not an ERROR. Logging it as an error is how a shutdown
    filled `error.log` with tracebacks that looked like the app breaking.
    """
    try:
        callback(value)
    except RuntimeError as exc:
        if "already deleted" in str(exc):
            Logger.debug("Background", f"{label} result dropped: screen closed.")
            return
        Logger.error("Background", f"{label} callback failed.", exc=exc)
    except Exception as exc:
        Logger.error("Background", f"{label} callback failed.", exc=exc)


def run_in_background(
    fn: Callable[[], Any],
    on_done: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    owner: Optional[QObject] = None,
    label: str = "",
    pool: Optional[QThreadPool] = None,
) -> BackgroundTask:
    """Run `fn` off the GUI thread; deliver the answer back on it.

    Returns the task so the caller can keep a reference. Keeping one matters:
    without it the `_Signals` object can be collected before the work
    finishes and the result is delivered to nobody.
    """
    task = BackgroundTask(fn, label=label, owner=owner)

    if owner is not None:
        alive = {"ok": True}

        def _died() -> None:
            alive["ok"] = False

        try:
            owner.destroyed.connect(_died)
        except Exception as exc:
            Logger.debug("Background", "Could not watch the owner", exc=exc)

        # `destroyed` fires *after* Qt has deleted the widget's children, so a
        # callback can already be too late by the time the flag flips. Closing
        # is the earlier, more useful signal for a window.
        closing = getattr(owner, "aboutToClose", None)
        if closing is not None:
            try:
                closing.connect(_died)
            except Exception as exc:
                Logger.debug("Background", "Owner has no usable close signal", exc=exc)

        def guard(callback):
            def _run(value):
                if not alive["ok"]:
                    return
                _deliver(callback, value, label)
            return _run
    else:
        def guard(callback):
            def _run(value):
                _deliver(callback, value, label)
            return _run

    if on_done is not None:
        task.signals.done.connect(guard(on_done))
    if on_error is not None:
        task.signals.failed.connect(guard(on_error))

    (pool or QThreadPool.globalInstance()).start(task)
    return task
