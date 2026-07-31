"""
Application Container Module
Provides dependency injection container for LeagueLoop core services.
"""
from typing import Optional

from services.api_handler import LCUClient
from services.asset_manager import AssetManager, ConfigManager
from services.automation import AutomationEngine
from services.account_manager import AccountManager, get_account_manager
from services.stats_scraper import StatsScraper, get_stats_scraper
from services.settings_service import SettingsService, get_settings_service
from services.league_service import LeagueService, get_league_service
from services.friend_service import FriendService, get_friend_service
from services.champion_service import ChampionService, get_champion_service
from services.draft_service import DraftService, get_draft_service
from services.window_service import WindowService, get_window_service
from services.notification_service import NotificationService, get_notification_service
from services.queue_service import QueueService, get_queue_service
from utils.logger import Logger


class ApplicationContainer:
    """Dependency injection container holding central service instances."""

    def __init__(self):
        self.config: ConfigManager = ConfigManager()
        self.assets: AssetManager = AssetManager()

        from core.state import State

        State.assets = self.assets

        self.lcu: LCUClient = LCUClient()
        self.scraper: StatsScraper = get_stats_scraper(
            mode=self.config.get("aram_mode", "ARAM")
        )

        # Service singletons
        self.settings_service: SettingsService = get_settings_service(self.config)
        self.league_service: LeagueService = get_league_service(self.lcu)
        self.friend_service: FriendService = get_friend_service(
            self.settings_service, self.league_service
        )
        self.champion_service: ChampionService = get_champion_service(
            self.assets, self.scraper
        )
        self.draft_service: DraftService = get_draft_service(self.league_service)
        self.window_service: WindowService = get_window_service(self.settings_service)
        self.notification_service: NotificationService = get_notification_service()
        self.queue_service: QueueService = get_queue_service(
            self.settings_service, self.league_service
        )

        self.automation: Optional[AutomationEngine] = None
        self.account_manager: Optional[AccountManager] = None

    def initialize_automation(self, stop_callback=None) -> AutomationEngine:
        """Instantiates and configures the AutomationEngine."""
        self.automation = AutomationEngine(
            self.lcu,
            self.assets,
            self.config,
            log_func=lambda msg: Logger.info("Auto", msg),
            stop_func=stop_callback,
        )
        return self.automation

    def initialize_account_manager(
        self, launch_client_func=None
    ) -> AccountManager:
        """Instantiates and configures the AccountManager."""
        self.account_manager = get_account_manager(
            lcu=self.lcu, launch_client_func=launch_client_func
        )
        return self.account_manager
