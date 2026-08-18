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
        )
        return self.account_manager

    def shutdown(self) -> None:
        """Best-effort teardown of long-lived services."""
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
