import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core.container import ApplicationContainer


class TestContainerBootstrap(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.temp_dir.name, "test_bootstrap.db")
        self.container = ApplicationContainer(db_path=db_path)

    def tearDown(self):
        self.container.shutdown()
        self.temp_dir.cleanup()

    def test_bootstrap_initializes_core_services(self):
        with patch.object(self.container.assets, "start_loading") as mock_assets, \
             patch("services.local_api.start_api_server", return_value=("127.0.0.1", 8337)) as mock_api:
            self.container.bootstrap(
                start_assets=True,
                start_automation=True,
                start_client_state=False,
                start_api=True,
            )

            mock_assets.assert_called_once()
            self.assertIsNotNone(self.container.account_manager)
            self.assertIsNotNone(self.container.automation_controller)
            self.assertIsNotNone(self.container.automation)
            self.assertIsNotNone(self.container.client_state)
            mock_api.assert_called_once()

    def test_account_manager_syncs_state(self):
        self.container.bootstrap(start_assets=False, start_api=False)
        mgr = self.container.account_manager
        self.assertIsNotNone(mgr)
        self.assertIsNotNone(mgr.state_manager)

        # Adding / setting account state updates StateManager
        mgr._mark_active(0)
        st = self.container.state_manager.state
        self.assertIsNotNone(st.account)

    def test_kill_game_processes_helper(self):
        from services.account_manager import AccountManager

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            killed = AccountManager._kill_game_processes()
            self.assertTrue(killed)
            self.assertEqual(mock_run.call_count, 2)
