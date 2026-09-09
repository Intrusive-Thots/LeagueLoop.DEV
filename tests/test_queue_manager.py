import unittest
from unittest.mock import MagicMock

from services.queue_manager import (
    QueueManager,
    resolve_queue_id,
    resolve_mode_name,
    start_matchmaking,
    stop_matchmaking,
    create_lobby,
    update_available_lobby_types,
    get_categorized_lobby_types
)


class TestQueueManager(unittest.TestCase):

    def setUp(self):
        # Reset the singleton instance for each test so tests don't affect each other
        QueueManager._instance = None
        self.mgr = QueueManager.get_instance()

    def test_singleton_instance(self):
        """Test that get_instance always returns the same object."""
        instance1 = QueueManager.get_instance()
        instance2 = QueueManager.get_instance()
        self.assertIs(instance1, instance2)

    def test_resolve_queue_id_basic(self):
        """Test basic queue ID resolution from known static modes."""
        self.assertEqual(self.mgr.resolve_queue_id("ARAM"), 450)
        self.assertEqual(self.mgr.resolve_queue_id("Ranked Solo/Duo"), 420)
        self.assertEqual(self.mgr.resolve_queue_id("Draft Pick"), 400)

    def test_resolve_queue_id_case_insensitive(self):
        """Test queue ID resolution ignoring case."""
        self.assertEqual(self.mgr.resolve_queue_id("aram"), 450)
        self.assertEqual(self.mgr.resolve_queue_id("RANKED SOLO/DUO"), 420)

    def test_resolve_queue_id_fuzzy(self):
        """Test queue ID resolution with partial strings if supported."""
        # Baseline fuzzy match logic: checks if mode_lower in name.lower()
        self.assertEqual(self.mgr.resolve_queue_id("solo/duo"), 420)

    def test_resolve_queue_id_fallback(self):
        """Test that unknown or empty modes fallback to ARAM (450)."""
        self.assertEqual(self.mgr.resolve_queue_id(""), 450)
        self.assertEqual(self.mgr.resolve_queue_id(None), 450)
        self.assertEqual(self.mgr.resolve_queue_id("Super Secret Unknown Mode"), 450)

    def test_resolve_mode_name_basic(self):
        """Test basic mode name resolution from known static IDs."""
        self.assertEqual(self.mgr.resolve_mode_name(450), "ARAM")
        self.assertEqual(self.mgr.resolve_mode_name(420), "Ranked Solo/Duo")

    def test_resolve_mode_name_string_input(self):
        """Test mode name resolution when given a string integer."""
        self.assertEqual(self.mgr.resolve_mode_name("450"), "ARAM")
        self.assertEqual(self.mgr.resolve_mode_name("420"), "Ranked Solo/Duo")

    def test_resolve_mode_name_fallback(self):
        """Test fallback behavior for invalid or unknown IDs."""
        self.assertEqual(self.mgr.resolve_mode_name("not an int"), "ARAM")
        self.assertEqual(self.mgr.resolve_mode_name(99999), "Queue 99999")

    def test_start_matchmaking(self):
        """Test starting matchmaking logic."""
        # Unconnected LCU
        lcu_mock = MagicMock()
        lcu_mock.is_connected = False
        self.assertFalse(self.mgr.start_matchmaking(lcu_mock))

        # Connected LCU, success response (204)
        lcu_mock.is_connected = True
        mock_res = MagicMock()
        mock_res.status_code = 204
        lcu_mock.request.return_value = mock_res
        self.assertTrue(self.mgr.start_matchmaking(lcu_mock))
        lcu_mock.request.assert_called_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

        # Connected LCU, fail response (500)
        mock_res.status_code = 500
        self.assertFalse(self.mgr.start_matchmaking(lcu_mock))

        # Connected LCU, exception thrown
        lcu_mock.request.side_effect = Exception("Network error")
        self.assertFalse(self.mgr.start_matchmaking(lcu_mock))

    def test_stop_matchmaking(self):
        """Test stopping matchmaking logic."""
        # Unconnected LCU
        lcu_mock = MagicMock()
        lcu_mock.is_connected = False
        self.assertFalse(self.mgr.stop_matchmaking(lcu_mock))

        # Connected LCU, success response (204)
        lcu_mock.is_connected = True
        mock_res = MagicMock()
        mock_res.status_code = 204
        lcu_mock.request.return_value = mock_res
        self.assertTrue(self.mgr.stop_matchmaking(lcu_mock))
        lcu_mock.request.assert_called_with("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")

        # Connected LCU, exception thrown
        lcu_mock.request.side_effect = Exception("Network error")
        self.assertFalse(self.mgr.stop_matchmaking(lcu_mock))

    def test_create_lobby(self):
        """Test creating a lobby."""
        # Unconnected LCU
        lcu_mock = MagicMock()
        lcu_mock.is_connected = False
        self.assertFalse(self.mgr.create_lobby(lcu_mock, 450))

        # Connected LCU, success response (200)
        lcu_mock.is_connected = True
        mock_res = MagicMock()
        mock_res.status_code = 200
        lcu_mock.request.return_value = mock_res
        self.assertTrue(self.mgr.create_lobby(lcu_mock, 450))
        lcu_mock.request.assert_called_with("POST", "/lol-lobby/v2/lobby", {"queueId": 450})

        # Connected LCU, exception thrown
        lcu_mock.request.side_effect = Exception("Network error")
        self.assertFalse(self.mgr.create_lobby(lcu_mock, 450))

    def test_update_available_lobby_types_unconnected(self):
        """Test update returns cached groups when unconnected."""
        lcu_mock = MagicMock()
        lcu_mock.is_connected = False
        groups = self.mgr.update_available_lobby_types(lcu_mock)
        # Verify it returns the default baseline groups list length
        self.assertGreater(len(groups), 0)

    def test_update_available_lobby_types_connected(self):
        """Test update parses valid LCU data and updates maps."""
        lcu_mock = MagicMock()
        lcu_mock.is_connected = True
        mock_res = MagicMock()
        mock_res.status_code = 200

        # Simulate some queues
        mock_res.json.return_value = [
            {
                "id": 9999,
                "name": "Super Test Queue",
                "queueAvailability": "Available",
                "isCustom": False,
                "category": "PvP",
                "gameMode": "Classic"
            },
            {
                "id": 8888,
                "name": "Hidden Custom Queue",
                "queueAvailability": "Available",
                "isCustom": True,
            },
            {
                "id": 7777,
                "name": "Unavailable Queue",
                "queueAvailability": "Unavailable",
                "isCustom": False,
            }
        ]
        lcu_mock.request.return_value = mock_res

        # Capture current map size
        initial_id_count = len(self.mgr._queue_id_to_name)

        groups = self.mgr.update_available_lobby_types(lcu_mock)

        # The new queue should be categorized (likely 'Casual' since PvP/Classic, but let's just check mapping)
        self.assertEqual(self.mgr.resolve_mode_name(9999), "Super Test Queue")
        self.assertEqual(self.mgr.resolve_queue_id("Super Test Queue"), 9999)

        # Custom or unavailable shouldn't override standard handling if not already mapped,
        # but note our update function rebuilds from BASELINE_QUEUE_MAP each time, so it won't add them.
        self.assertEqual(self.mgr.resolve_mode_name(8888), "Queue 8888")
        self.assertEqual(self.mgr.resolve_mode_name(7777), "Queue 7777")

    def test_global_helper_functions(self):
        """Verify that the module-level helper functions delegate to the manager instance."""
        # We can just check they don't crash and return expected types/values
        self.assertEqual(resolve_queue_id("ARAM"), 450)
        self.assertEqual(resolve_mode_name(450), "ARAM")
        self.assertIsInstance(get_categorized_lobby_types(), list)

        # For LCU dependant ones, pass unconnected mock
        lcu_mock = MagicMock()
        lcu_mock.is_connected = False
        self.assertFalse(start_matchmaking(lcu_mock))
        self.assertFalse(stop_matchmaking(lcu_mock))
        self.assertFalse(create_lobby(lcu_mock, 450))

        groups = update_available_lobby_types(lcu_mock)
        self.assertIsInstance(groups, list)


if __name__ == '__main__':
    unittest.main()
