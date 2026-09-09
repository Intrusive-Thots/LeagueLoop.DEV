import unittest
from unittest.mock import MagicMock, patch
from typing import List, Tuple

from services.queue_manager import (
    QueueManager,
    BASELINE_QUEUE_MAP,
    BASELINE_NAME_TO_ID,
    BASELINE_GROUPS
)


class TestQueueManager(unittest.TestCase):
    def setUp(self):
        # Reset the singleton instance before each test to ensure isolation
        QueueManager._instance = None
        self.manager = QueueManager.get_instance()

    def test_get_instance(self):
        """Test that get_instance returns a singleton."""
        instance1 = QueueManager.get_instance()
        instance2 = QueueManager.get_instance()
        self.assertIs(instance1, instance2)
        self.assertIs(instance1, self.manager)

    def test_initial_state(self):
        """Test the initial state of the QueueManager."""
        self.assertEqual(self.manager._queue_id_to_name, BASELINE_QUEUE_MAP)
        self.assertEqual(self.manager._name_to_queue_id, BASELINE_NAME_TO_ID)
        self.assertEqual(self.manager._categorized_groups, BASELINE_GROUPS)

    def test_resolve_queue_id(self):
        """Test resolving mode string to queue ID."""
        # Empty string defaults to ARAM (450)
        self.assertEqual(self.manager.resolve_queue_id(""), 450)
        self.assertEqual(self.manager.resolve_queue_id(None), 450)

        # Exact match
        self.assertEqual(self.manager.resolve_queue_id("Ranked Solo/Duo"), 420)
        self.assertEqual(self.manager.resolve_queue_id("ARAM"), 450)

        # Case insensitive match
        self.assertEqual(self.manager.resolve_queue_id("ranked solo/duo"), 420)

        # Alias match
        self.assertEqual(self.manager.resolve_queue_id("Ranked Solo"), 420)

        # Fuzzy match
        self.assertEqual(self.manager.resolve_queue_id("Draft"), 400) # Match "Draft Pick"
        self.assertEqual(self.manager.resolve_queue_id("blind"), 450) # Not found, returns default 450

    def test_resolve_mode_name(self):
        """Test resolving queue ID to mode name."""
        # Valid ID
        self.assertEqual(self.manager.resolve_mode_name(420), "Ranked Solo/Duo")
        self.assertEqual(self.manager.resolve_mode_name(450), "ARAM")

        # Invalid ID / String
        self.assertEqual(self.manager.resolve_mode_name("not_an_int"), "ARAM")
        self.assertEqual(self.manager.resolve_mode_name(None), "ARAM")

        # Unknown valid int ID
        self.assertEqual(self.manager.resolve_mode_name(9999), "Queue 9999")

    def test_get_categorized_groups(self):
        """Test retrieving categorized groups."""
        groups = self.manager.get_categorized_groups()
        self.assertIsInstance(groups, list)
        self.assertEqual(groups, BASELINE_GROUPS)

        # Ensure it returns a copy
        self.assertIsNot(groups, self.manager._categorized_groups)

        # Modifying returned list shouldn't modify internal list
        groups.clear()
        self.assertNotEqual(self.manager._categorized_groups, [])

    def test_update_available_lobby_types_no_lcu(self):
        """Test update_available_lobby_types with no LCU connection."""
        groups = self.manager.update_available_lobby_types(None)
        self.assertEqual(groups, BASELINE_GROUPS)

        lcu_mock = MagicMock()
        lcu_mock.is_connected = False
        groups = self.manager.update_available_lobby_types(lcu_mock)
        self.assertEqual(groups, BASELINE_GROUPS)

    def test_update_available_lobby_types_failed_request(self):
        """Test update_available_lobby_types when request fails or returns non-200."""
        lcu_mock = MagicMock()
        lcu_mock.is_connected = True

        # Test 1: returns None
        lcu_mock.request.return_value = None
        self.assertEqual(self.manager.update_available_lobby_types(lcu_mock), BASELINE_GROUPS)

        # Test 2: non-200 status
        bad_res = MagicMock()
        bad_res.status_code = 404
        lcu_mock.request.return_value = bad_res
        self.assertEqual(self.manager.update_available_lobby_types(lcu_mock), BASELINE_GROUPS)

        # Test 3: non-list json
        good_res_bad_json = MagicMock()
        good_res_bad_json.status_code = 200
        good_res_bad_json.json.return_value = {"not": "a list"}
        lcu_mock.request.return_value = good_res_bad_json
        self.assertEqual(self.manager.update_available_lobby_types(lcu_mock), BASELINE_GROUPS)

    def test_update_available_lobby_types_success(self):
        """Test successful dynamic update of lobby types from LCU."""
        lcu_mock = MagicMock()
        lcu_mock.is_connected = True

        res = MagicMock()
        res.status_code = 200
        res.json.return_value = [
            # Ranked
            {"id": 420, "name": "Ranked Solo/Duo", "queueAvailability": "Available", "isCustom": False, "isRanked": True},
            # ARAM
            {"id": 450, "name": "ARAM", "queueAvailability": "Available", "isCustom": False, "gameMode": "ARAM"},
            # Casual (pvp, classic)
            {"id": 400, "name": "Draft Pick", "queueAvailability": "Available", "isCustom": False, "category": "PvP", "gameMode": "Classic"},
            # TFT
            {"id": 1090, "name": "TFT Normal", "queueAvailability": "Available", "isCustom": False, "gameMode": "TFT"},
            # Arena
            {"id": 1700, "name": "Arena", "queueAvailability": "Available", "isCustom": False, "gameMode": "CHERRY"},
            # Rotating / Special
            {"id": 900, "name": "URF", "queueAvailability": "Available", "isCustom": False},

            # Unavailable / Custom - Should be skipped
            {"id": 999, "name": "Custom Game", "queueAvailability": "Available", "isCustom": True},
            {"id": 888, "name": "Dead Queue", "queueAvailability": "Unavailable", "isCustom": False}
        ]
        lcu_mock.request.return_value = res

        # Run the update
        groups = self.manager.update_available_lobby_types(lcu_mock)

        # Verify LCU request
        lcu_mock.request.assert_called_once_with("GET", "/lol-game-queues/v1/queues", silent=True)

        # Check that groups is updated properly (structure: List[Tuple[str, List[str]]])
        expected_groups = [
            ("Ranked", ["Ranked Solo/Duo"]),
            ("Casual", ["Draft Pick"]),
            ("ARAM", ["ARAM"]),
            ("Arena", ["Arena"]),
            ("Rotating / Special", ["URF"]),
            ("TFT", ["TFT Normal"])
        ]
        self.assertEqual(groups, expected_groups)
        self.assertEqual(self.manager._categorized_groups, expected_groups)

        # Check dynamic mapping updates
        self.assertEqual(self.manager.resolve_queue_id("Ranked Solo/Duo"), 420)
        self.assertEqual(self.manager.resolve_queue_id("ARAM"), 450)
        self.assertEqual(self.manager.resolve_mode_name(400), "Draft Pick")

    def test_start_matchmaking(self):
        """Test start_matchmaking."""
        # No LCU or not connected
        self.assertFalse(self.manager.start_matchmaking(None))

        lcu_mock = MagicMock()
        lcu_mock.is_connected = False
        self.assertFalse(self.manager.start_matchmaking(lcu_mock))

        # Connected and success
        lcu_mock.is_connected = True
        res = MagicMock()
        res.status_code = 204
        lcu_mock.request.return_value = res
        self.assertTrue(self.manager.start_matchmaking(lcu_mock))
        lcu_mock.request.assert_called_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

        # Connected but request fails / returns bad code
        res.status_code = 500
        self.assertFalse(self.manager.start_matchmaking(lcu_mock))

        lcu_mock.request.side_effect = Exception("HTTP Error")
        self.assertFalse(self.manager.start_matchmaking(lcu_mock))

    def test_stop_matchmaking(self):
        """Test stop_matchmaking."""
        # No LCU or not connected
        self.assertFalse(self.manager.stop_matchmaking(None))

        lcu_mock = MagicMock()
        lcu_mock.is_connected = False
        self.assertFalse(self.manager.stop_matchmaking(lcu_mock))

        # Connected and success
        lcu_mock.is_connected = True
        res = MagicMock()
        res.status_code = 200
        lcu_mock.request.return_value = res
        self.assertTrue(self.manager.stop_matchmaking(lcu_mock))
        lcu_mock.request.assert_called_with("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")

        # Connected but request fails / returns bad code
        res.status_code = 500
        self.assertFalse(self.manager.stop_matchmaking(lcu_mock))

        lcu_mock.request.side_effect = Exception("HTTP Error")
        self.assertFalse(self.manager.stop_matchmaking(lcu_mock))

    def test_create_lobby(self):
        """Test create_lobby."""
        # No LCU or not connected
        self.assertFalse(self.manager.create_lobby(None, 450))

        lcu_mock = MagicMock()
        lcu_mock.is_connected = False
        self.assertFalse(self.manager.create_lobby(lcu_mock, 450))

        # Connected and success
        lcu_mock.is_connected = True
        res = MagicMock()
        res.status_code = 200
        lcu_mock.request.return_value = res
        self.assertTrue(self.manager.create_lobby(lcu_mock, 450))
        lcu_mock.request.assert_called_with("POST", "/lol-lobby/v2/lobby", {"queueId": 450})

        # Connected but request fails / returns bad code
        res.status_code = 500
        self.assertFalse(self.manager.create_lobby(lcu_mock, 450))

        lcu_mock.request.side_effect = Exception("HTTP Error")
        self.assertFalse(self.manager.create_lobby(lcu_mock, 450))


class TestQueueManagerGlobalHelpers(unittest.TestCase):
    """Test module-level convenience helper functions wrap QueueManager correctly."""

    @patch('services.queue_manager._mgr')
    def test_update_available_lobby_types(self, mock_mgr):
        from services.queue_manager import update_available_lobby_types
        lcu = MagicMock()
        update_available_lobby_types(lcu)
        mock_mgr.update_available_lobby_types.assert_called_once_with(lcu)

    @patch('services.queue_manager._mgr')
    def test_get_categorized_lobby_types(self, mock_mgr):
        from services.queue_manager import get_categorized_lobby_types
        get_categorized_lobby_types()
        mock_mgr.get_categorized_groups.assert_called_once()

    @patch('services.queue_manager._mgr')
    def test_resolve_queue_id(self, mock_mgr):
        from services.queue_manager import resolve_queue_id
        resolve_queue_id("ARAM", None)
        mock_mgr.resolve_queue_id.assert_called_once_with("ARAM", None)

    @patch('services.queue_manager._mgr')
    def test_resolve_mode_name(self, mock_mgr):
        from services.queue_manager import resolve_mode_name
        resolve_mode_name(450, None)
        mock_mgr.resolve_mode_name.assert_called_once_with(450, None)

    @patch('services.queue_manager._mgr')
    def test_start_matchmaking(self, mock_mgr):
        from services.queue_manager import start_matchmaking
        lcu = MagicMock()
        start_matchmaking(lcu)
        mock_mgr.start_matchmaking.assert_called_once_with(lcu)

    @patch('services.queue_manager._mgr')
    def test_stop_matchmaking(self, mock_mgr):
        from services.queue_manager import stop_matchmaking
        lcu = MagicMock()
        stop_matchmaking(lcu)
        mock_mgr.stop_matchmaking.assert_called_once_with(lcu)

    @patch('services.queue_manager._mgr')
    def test_create_lobby(self, mock_mgr):
        from services.queue_manager import create_lobby
        lcu = MagicMock()
        create_lobby(lcu, 450)
        mock_mgr.create_lobby.assert_called_once_with(lcu, 450)
