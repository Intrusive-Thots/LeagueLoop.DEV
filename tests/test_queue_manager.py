import pytest
from unittest.mock import MagicMock
from services.queue_manager import QueueManager

@pytest.fixture
def queue_manager():
    return QueueManager()

def test_start_matchmaking_no_lcu(queue_manager):
    assert queue_manager.start_matchmaking(None) is False

def test_start_matchmaking_not_connected(queue_manager):
    lcu_mock = MagicMock()
    lcu_mock.is_connected = False
    assert queue_manager.start_matchmaking(lcu_mock) is False

def test_start_matchmaking_success_200(queue_manager):
    lcu_mock = MagicMock()
    lcu_mock.is_connected = True
    res_mock = MagicMock()
    res_mock.status_code = 200
    lcu_mock.request.return_value = res_mock

    assert queue_manager.start_matchmaking(lcu_mock) is True
    lcu_mock.request.assert_called_once_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

def test_start_matchmaking_success_204(queue_manager):
    lcu_mock = MagicMock()
    lcu_mock.is_connected = True
    res_mock = MagicMock()
    res_mock.status_code = 204
    lcu_mock.request.return_value = res_mock

    assert queue_manager.start_matchmaking(lcu_mock) is True
    lcu_mock.request.assert_called_once_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

def test_start_matchmaking_failure_status(queue_manager):
    lcu_mock = MagicMock()
    lcu_mock.is_connected = True
    res_mock = MagicMock()
    res_mock.status_code = 400
    lcu_mock.request.return_value = res_mock

    assert queue_manager.start_matchmaking(lcu_mock) is False
    lcu_mock.request.assert_called_once_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

def test_start_matchmaking_none_response(queue_manager):
    lcu_mock = MagicMock()
    lcu_mock.is_connected = True
    lcu_mock.request.return_value = None

    assert queue_manager.start_matchmaking(lcu_mock) is False
    lcu_mock.request.assert_called_once_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

def test_start_matchmaking_exception(queue_manager):
    lcu_mock = MagicMock()
    lcu_mock.is_connected = True
    lcu_mock.request.side_effect = Exception("Test Error")

    assert queue_manager.start_matchmaking(lcu_mock) is False
    lcu_mock.request.assert_called_once_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")
