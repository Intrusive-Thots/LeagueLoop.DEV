"""
ApplicationContainer — lightweight dependency injection for LeagueLoop.

Centralizes construction of core services so LeagueLoopApp no longer owns
every dependency. Enables future testing and PySide6 migration without
rewriting the app shell.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

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

    def bootstrap(
        self,
        *,
        launch_client_func=None,
        start_assets: bool = True,
        start_automation: bool = True,
        start_client_state: bool = False,
        start_api: bool = True,
        api_port: int = 8337,
        log_func=None,
        stop_func=None,
        stats_func=None,
        window_func=None,
        queue_func=None,
    ) -> "ApplicationContainer":
        """
        Unified bootstrap sequence (composition root) for all app shells.
        Constructs and coordinates the full service graph:
        1. Assets loading & State.assets sync
        2. Account manager
        3. Automation engine & lifecycle controller
        4. Client state service (syncs LCU into ApplicationState)
        5. Local API server (port 8337 for mobile companion & local integrations)
        """
        from utils.logger import Logger

        # 1. Assets
        if start_assets and hasattr(self, "assets") and self.assets:
            try:
                self.assets.start_loading()
            except Exception as exc:
                Logger.warning("Container", f"Asset loading start failed: {exc}")

        try:
            from core.state import State
            State.assets = self.assets
        except Exception:
            pass

        # 2. Account Manager
        self.create_account_manager(launch_client_func=launch_client_func)

        # 3. Automation Controller & Engine
        self.create_automation_controller(
            log_func=log_func,
            stop_func=stop_func,
            stats_func=stats_func,
            window_func=window_func,
            queue_func=queue_func,
        )
        if start_automation and self.automation_controller is not None:
            try:
                self.automation_controller.apply_config()
            except Exception as exc:
                Logger.warning("Container", f"Could not apply automation config: {exc}")

        # 4. Client state service
        self.create_client_state_service(autostart=start_client_state)

        # 5. Local API Server
        if start_api:
            try:
                from services.local_api import start_api_server
                self._api_ip, self._api_port = start_api_server(self, port=api_port, bind_local=True)
            except Exception as exc:
                Logger.warning("Container", f"Local API server start failed: {exc}")

        return self

    def shutdown(self) -> None:
        """Best-effort teardown of long-lived services."""
        self.automation_controller = None
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
