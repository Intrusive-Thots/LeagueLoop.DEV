"""
ApplicationContainer — lightweight dependency injection for LeagueLoop.

Centralizes construction of core services so LeagueLoopApp no longer owns
every dependency. Enables testing the services without standing up a UI.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import time

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
        # Move any data an older dev run left in the repository into AppData
        # BEFORE ConfigManager reads it, or the app starts from the wrong copy
        # and the migration looks like it lost the user's settings.
        try:
            from utils.path_utils import migrate_data_from_project_root

            moved = migrate_data_from_project_root()
            if moved:
                Logger.info(
                    "Container",
                    "Moved user data out of the project folder and into "
                    "AppData: {}".format(", ".join(moved)),
                )
        except Exception as exc:
            Logger.warning(
                "Container",
                "Could not move user data out of the project folder.", exc=exc,
            )

        self.config: ConfigManager = ConfigManager()
        # Fold retired keys into the live ones before any service reads them.
        try:
            self.config.migrate_legacy_keys()
        except Exception as exc:
            Logger.warning(
                "Container",
                "Could not migrate retired settings; an old option may still "
                "be in effect.",
                exc=exc,
            )
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

    # `create_client_window_tracker()` is gone with the Qt shell. The tracker
    # existed to tell the PySide6 companion panel where the League Client's
    # window was; nothing in the CustomTkinter shell reads `ClientWindowState`,
    # so keeping it meant a thread enumerating windows five times a second for
    # nobody.

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
        after the views exist — `core.main.LeagueLoopApp` does.

        Failures are reported and swallowed per-service. One unavailable
        subsystem must degrade its own screen, not prevent the app starting.
        """
        errors = []
        started: list = []
        began = time.time()
        Logger.info("Container", "Bootstrapping services…")

        if start_assets:
            try:
                self.assets.start_loading()
                started.append("assets")
            except Exception as exc:
                errors.append(("assets", exc))

        try:
            self.create_automation(**(automation_hooks or {}))
            self.create_automation_controller()
            started.append("automation")
        except Exception as exc:
            errors.append(("automation", exc))

        try:
            self.create_account_manager(launch_client_func=launch_client_func)
            started.append("accounts")
        except Exception as exc:
            errors.append(("accounts", exc))

        try:
            self.create_client_state_service(autostart=start_client_state)
            started.append("client state")
        except Exception as exc:
            errors.append(("client state", exc))

        if apply_automation_config and self.automation_controller is not None:
            try:
                self.automation_controller.apply_config()
            except Exception as exc:
                errors.append(("automation config", exc))

        for name, exc in errors:
            Logger.error(
                "Container",
                f"Service '{name}' did not start — every feature that needs "
                f"it is unavailable for this run.",
                exc=exc, service=name,
            )
        Logger.info(
            "Container",
            "Bootstrap finished in {:.2f}s — started: {}; failed: {}".format(
                time.time() - began,
                ", ".join(started) or "nothing",
                ", ".join(n for n, _ in errors) or "none",
            ),
            started=started, failed=[n for n, _ in errors],
        )
        self.bootstrap_errors = errors

        return self

    def failure_reason(self, service: str) -> str:
        """One sentence saying why a service is missing, for the UI to show.

        A screen that depends on a failed service should say so in the screen,
        not leave the user with a feature that quietly does nothing while the
        reason sits in a log file they will never open.
        """
        for name, exc in self.bootstrap_errors:
            if name == service:
                detail = str(exc).strip() or type(exc).__name__
                return "The {} service did not start: {}".format(service, detail)
        return ""

    def shutdown(self) -> None:
        """Best-effort teardown of long-lived services."""
        Logger.info("Container", "Shutting services down…")
        self.automation_controller = None
        # The asset manager starts a pool of download workers in its
        # constructor and nothing ever stopped them; every container built in
        # a test leaked a fresh set.
        if getattr(self, "assets", None) is not None:
            try:
                self.assets.shutdown()
            except Exception as exc:
                Logger.warning(
                    "Container", "Could not shut down the asset manager cleanly.", exc=exc
                )
        if getattr(self, "client_state", None) is not None:
            try:
                self.client_state.stop()
            except Exception as exc:
                Logger.warning(
                    "Container", "Could not shut down the client state service cleanly.", exc=exc
                )
            self.client_state = None
        if self.automation is not None:
            try:
                self.automation.stop()
            except Exception as exc:
                Logger.warning(
                    "Container", "Could not shut down the automation engine cleanly.", exc=exc
                )
            self.automation = None
        if hasattr(self, "db") and self.db is not None:
            try:
                self.db.close()
            except Exception as exc:
                Logger.warning(
                    "Container", "Could not shut down the database cleanly.", exc=exc
                )
