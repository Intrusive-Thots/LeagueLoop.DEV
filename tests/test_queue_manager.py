import unittest
from unittest.mock import MagicMock
from src.services.queue_manager import QueueManager

class TestQueueManager(unittest.TestCase):
    def setUp(self):
        # Reset the singleton instance to ensure clean state
        QueueManager._instance = None
        self.queue_manager = QueueManager.get_instance()

    def test_start_matchmaking_no_lcu(self):
        result = self.queue_manager.start_matchmaking(None)
        self.assertFalse(result)

    def test_start_matchmaking_disconnected_lcu(self):
        mock_lcu = MagicMock()
        mock_lcu.is_connected = False
        result = self.queue_manager.start_matchmaking(mock_lcu)
        self.assertFalse(result)

    def test_start_matchmaking_success_200(self):
        mock_lcu = MagicMock()
        mock_lcu.is_connected = True
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_lcu.request.return_value = mock_response

        result = self.queue_manager.start_matchmaking(mock_lcu)

        self.assertTrue(result)
        mock_lcu.request.assert_called_once_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

    def test_start_matchmaking_success_204(self):
        mock_lcu = MagicMock()
        mock_lcu.is_connected = True
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_lcu.request.return_value = mock_response

        result = self.queue_manager.start_matchmaking(mock_lcu)

        self.assertTrue(result)
        mock_lcu.request.assert_called_once_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

    def test_start_matchmaking_failure_status(self):
        mock_lcu = MagicMock()
        mock_lcu.is_connected = True
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_lcu.request.return_value = mock_response

        result = self.queue_manager.start_matchmaking(mock_lcu)

        self.assertFalse(result)
        mock_lcu.request.assert_called_once_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

    def test_start_matchmaking_none_response(self):
        mock_lcu = MagicMock()
        mock_lcu.is_connected = True
        mock_lcu.request.return_value = None

        result = self.queue_manager.start_matchmaking(mock_lcu)

        self.assertFalse(result)
        mock_lcu.request.assert_called_once_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

    def test_start_matchmaking_exception(self):
        mock_lcu = MagicMock()
        mock_lcu.is_connected = True
        mock_lcu.request.side_effect = Exception("Test Exception")

        result = self.queue_manager.start_matchmaking(mock_lcu)

        self.assertFalse(result)
        mock_lcu.request.assert_called_once_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

if __name__ == '__main__':
    unittest.main()
