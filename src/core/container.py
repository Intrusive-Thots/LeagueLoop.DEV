"""
ApplicationContainer — lightweight dependency injection for LeagueLoop.

Centralizes construction of core services so LeagueLoopApp no longer owns
every dependency. Enables future testing and PySide6 migration without
rewriting the app shell.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from utils.logger import Logger

if TYPE_CHECKING:
    from services.api_handler import LCUClient
    from services.asset_manager import AssetManager
    from services.config_manager import ConfigManager
    from services.automation import AutomationEngine
    from services.account_manager import AccountManager
    from services.stats_scraper import StatsScraper
    from services.database import DatabaseService


class ApplicationContainer:
    """Owns and exposes the main service graph."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        from services.asset_manager import AssetManager
        from services.config_manager import ConfigManager
        from services.api_handler import LCUClient
        from services.stats_scraper import StatsScraper
        from services.database import DatabaseService
        from core.events import EventBus
        from core.state import StateManager

        self.bus: EventBus = EventBus
        self.state_manager: StateManager = StateManager(bus=self.bus)
        self.config: ConfigManager = ConfigManager()
        self.assets: AssetManager = AssetManager()
        self.lcu: LCUClient = LCUClient()
        self.db: DatabaseService = DatabaseService(db_path=db_path) if db_path else DatabaseService()
        self.scraper: StatsScraper = StatsScraper(
            mode=self.config.get("aram_mode", "ARAM")
        )
        self.automation: Optional[AutomationEngine] = None
        self.account_manager: Optional[AccountManager] = None
        self.client_state = None
        self.automation_controller = None
        self.bootstrap_errors: list = []

    def create_automation(
        self,
        *,
        stop_func=None,
        stats_func=None,
        window_func=None,
        queue_func=None,
        log_func=None,
    ) -> "AutomationEngine":
        from services.automation import AutomationEngine

        self.automation = AutomationEngine(
            self.lcu,
            self.assets,
            self.config,
            log_func=log_func,
            stop_func=stop_func,
            stats_func=stats_func,
            window_func=window_func,
            queue_func=queue_func,
            db=self.db,
        )
        return self.automation

    def create_account_manager(self, launch_client_func=None) -> "AccountManager":
        from services.account_manager import AccountManager

        self.account_manager = AccountManager(
            lcu=self.lcu,
            launch_client_func=launch_client_func,
            state_manager=self.state_manager,
        )
        return self.account_manager

    def create_automation_controller(self, **kwargs):
        """
        Build the engine and the controller that owns its lifecycle.

        The Qt shell never called `create_automation()`, so every automation
        toggle wrote a config key that nothing read at runtime.
        """
        from services.automation_controller import AutomationController

        if self.automation is None:
            self.create_automation(**kwargs)
        self.automation_controller = AutomationController(
            self.automation, self.state_manager, self.config
        )
        return self.automation_controller

    def create_client_state_service(self, autostart: bool = False, **kwargs):
        """
        Mirror the League Client into `ApplicationState`.

        Without this the state model has no producer at all: every view that
        renders from state shows its default (disconnected, idle) no matter
        what the client is doing.

        Does **not** start polling by default. The service only publishes
        changes, so if it runs before the UI has subscribed, the first batch
        of values is delivered to nobody and the shell sits on its defaults
        until the client next does something. Start it once the views exist.
        """
        from services.client_state_service import ClientStateService

        self.client_state = ClientStateService(
            self.lcu, self.state_manager,
            automation_controller=self.automation_controller,
            **kwargs
        )
        if autostart:
            self.client_state.start()
        return self.client_state

    # ------------------------------------------------------------ bootstrap
    def bootstrap(
        self,
        *,
        launch_client_func=None,
        automation_hooks: Optional[dict] = None,
        start_assets: bool = True,
        start_client_state: bool = False,
        apply_automation_config: bool = False,
        start_automation: bool = True,
        start_api: bool = True,
        **kwargs,
    ) -> "ApplicationContainer":
        """
        Bring every lazily-created service up, once, in one place.

        `__init__` only constructs the cheap services. Everything else — the
        automation engine, the account manager, asset downloading, the LCU
        state poller — used to be started imperatively by `core/main.py`, the
        CustomTkinter shell. The Qt shell built a container and a window and
        never reimplemented that sequence, so those services simply did not
        exist there: automation toggles wrote config keys nothing read,
        `champ_data` stayed empty so four screens had no champions, and the
        Accounts screen came up permanently disabled.

        That was the same mistake four times. Both shells now call this, so a
        service added here reaches both by construction.

        `start_client_state` is off by default and deliberately so: the state
        service only publishes *changes*, so starting it before the UI has
        subscribed means the first values are delivered to nobody. Start it
        after the views exist — `ui.qt.app.application.build()` does.

        Failures are reported and swallowed per-service. One unavailable
        subsystem must degrade its own screen, not prevent the app starting.
        """
        errors = []

        if start_assets:
            try:
                self.assets.start_loading()
            except Exception as exc:
                errors.append(("assets", exc))

        try:
            self.create_automation(**(automation_hooks or {}))
            self.create_automation_controller()
        except Exception as exc:
            errors.append(("automation", exc))

        try:
            self.create_account_manager(launch_client_func=launch_client_func)
        except Exception as exc:
            errors.append(("accounts", exc))

        try:
            self.create_client_state_service(autostart=start_client_state)
        except Exception as exc:
            errors.append(("client state", exc))

        if start_api:
            try:
                from services import local_api
                local_api.start_api_server(self)
            except Exception as exc:
                errors.append(("api server", exc))

        if apply_automation_config and self.automation_controller is not None:
            try:
                self.automation_controller.apply_config()
            except Exception as exc:
                errors.append(("automation config", exc))

        for name, exc in errors:
            Logger.error("Container", f"{name} unavailable: {exc}")
        self.bootstrap_errors = errors

        return self

    def shutdown(self) -> None:
        """Best-effort teardown of long-lived services."""
        self.automation_controller = None
        # The asset manager starts a pool of download workers in its
        # constructor and nothing ever stopped them; every container built in
        # a test leaked a fresh set.
        if getattr(self, "assets", None) is not None:
            try:
                self.assets.shutdown()
            except Exception:
                pass
        if getattr(self, "client_state", None) is not None:
            try:
                self.client_state.stop()
            except Exception:
                pass
            self.client_state = None
        if self.automation is not None:
            try:
                self.automation.stop()
            except Exception:
                pass
            self.automation = None
        if hasattr(self, "db") and self.db is not None:
            try:
                self.db.close()
            except Exception:
                pass
