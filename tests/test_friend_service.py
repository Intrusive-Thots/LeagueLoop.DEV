import unittest
from unittest.mock import MagicMock, patch
from core.events import EventBus
from services.friend_service import FriendService

class TestFriendService(unittest.TestCase):
    def setUp(self):
        # Clear EventBus to avoid side effects between tests
        EventBus._listeners.clear()
        self.mock_settings = MagicMock()
        self.mock_league = MagicMock()

    def test_load_config(self):
        self.mock_settings.get.return_value = [
            {"name": "Alice", "enabled": True},
            {"name": "Bob", "enabled": False}
        ]
        service = FriendService(self.mock_settings, self.mock_league)
        self.assertTrue(service.get_auto_join_status("Alice"))
        self.assertFalse(service.get_auto_join_status("Bob"))
        self.assertFalse(service.get_auto_join_status("Charlie"))

    def test_on_auto_join_list_changed(self):
        service = FriendService(self.mock_settings, self.mock_league)
        
        # Register a mock listener for the emitted event
        mock_listener = MagicMock()
        EventBus.on("friends_state_changed", mock_listener)
        
        self.mock_settings.get.return_value = [{"name": "Charlie", "enabled": True}]
        EventBus.emit("setting_changed:auto_join_list", [{"name": "Charlie", "enabled": True}])
        
        self.assertTrue(service.get_auto_join_status("Charlie"))
        mock_listener.assert_called_once()

    @patch("threading.Thread")
    def test_fetch_friends_not_connected(self, mock_thread):
        self.mock_league.is_connected = False
        service = FriendService(self.mock_settings, self.mock_league)
        service.fetch_friends()
        mock_thread.assert_not_called()

    def test_process_friends(self):
        service = FriendService(self.mock_settings, self.mock_league)
        friends = [
            {"name": "Bob", "availability": "offline", "puuid": "2"},
            {"name": "Alice", "availability": "chat", "puuid": "1"}
        ]
        
        mock_emit = MagicMock()
        with patch.object(EventBus, "emit", mock_emit):
            service._process_friends(friends)
            
            cached = service.get_friends()
            self.assertEqual(len(cached), 2)
            # Alice is online so she should be first
            self.assertEqual(cached[0]["name"], "Alice")
            self.assertEqual(cached[1]["name"], "Bob")
            mock_emit.assert_called_once_with("friends_state_changed")

    def test_merge_friend_delta(self):
        service = FriendService(self.mock_settings, self.mock_league)
        service._friends_cache = [
            {"name": "Alice", "availability": "chat", "puuid": "1"}
        ]
        
        delta = {"puuid": "1", "availability": "away"}
        service._on_friends_update(delta)
        
        cached = service.get_friends()
        self.assertEqual(cached[0]["availability"], "away")
