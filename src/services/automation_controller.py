"""
AutomationController — owns the automation engine's lifecycle.

The Qt shell never created `AutomationEngine` at all. `create_automation()`
was called from `core/main.py` only, so in the Qt app `container.automation`
was `None`, every toggle wrote a config key that nothing was reading at
runtime, and both `stop_requested` signals were connected to nothing. The
switches looked live and did nothing.

This puts the lifecycle in one place, with `AutomationState` published so the
header and the draft screen can report what is actually happening instead of
their defaults.
"""
from __future__ import annotations

from typing import Any, Optional

from utils.logger import Logger

#: Config key for the master switch shown at the top of the Automation screen.
MASTER_KEY = "automation_master"


class AutomationController:
    """Start/stop/pause the engine and keep `AutomationState` truthful."""

    def __init__(self, engine: Any, state_manager: Any, config: Any = None):
        self._engine = engine
        self._state = state_manager
        self._config = config

    # ------------------------------------------------------------- lifecycle
    @property
    def engine(self) -> Any:
        return self._engine

    @property
    def running(self) -> bool:
        return bool(getattr(self._engine, "running", False))

    def master_enabled(self) -> bool:
        if self._config is None:
            return False
        try:
            return bool(self._config.get(MASTER_KEY, True))
        except Exception:
            return False

    def apply_config(self) -> None:
        """
        Bring the engine in line with the master switch.

        Called at startup so the app comes up in the state the user left it,
        rather than requiring them to toggle the switch once per launch to
        make anything happen.
        """
        self.start() if self.master_enabled() else self.stop()

    def start(self) -> None:
        if self._engine is None or self.running:
            self.publish()
            return
        try:
            self._engine.start()
        except Exception as exc:
            Logger.error("Automation", f"Could not start: {exc}")
            self.publish(last_error=str(exc))
            return
        self.publish()

    def stop(self) -> None:
        if self._engine is None:
            self.publish()
            return
        try:
            self._engine.stop()
        except Exception as exc:
            Logger.error("Automation", f"Could not stop: {exc}")
        self.publish()

    def set_master(self, enabled: bool) -> None:
        """The master switch, as a single call the views can bind to."""
        if self._config is not None:
            try:
                self._config.set(MASTER_KEY, bool(enabled))
            except Exception:
                pass
        self.start() if enabled else self.stop()

    def pause(self, paused: bool = True) -> None:
        if self._engine is None:
            return
        try:
            self._engine.pause() if paused else self._engine.resume()
        except Exception as exc:
            Logger.debug("Automation", f"pause({paused}) failed: {exc}")
        self.publish()

    # --------------------------------------------------------------- publish
    def publish(self, last_error: Optional[str] = None) -> None:
        """Mirror the engine's real flags into `AutomationState`."""
        if self._state is None:
            return

        def cfg(key: str, default: bool) -> bool:
            if self._config is None:
                return default
            try:
                return bool(self._config.get(key, default))
            except Exception:
                return default

        fields = {
            "running": self.running,
            "paused": bool(getattr(self._engine, "paused", False)),
            "auto_accept": cfg("auto_accept", False),
            "auto_lock": cfg("auto_lock_in", False),
            "auto_requeue": cfg("auto_requeue", False),
            "auto_skin": cfg("auto_random_skin", True),
        }
        if last_error is not None:
            fields["last_error"] = last_error
        try:
            self._state.update_automation(**fields)
        except Exception as exc:
            Logger.debug("Automation", f"publish failed: {exc}")
