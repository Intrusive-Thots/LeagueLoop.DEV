"""
Tests for the Queue Manager Service.

Ensures that queue IDs and names map correctly natively and when dynamically
updated from the LCU. Also validates matchmaking dispatch functions.
"""

import pytest
from unittest.mock import MagicMock

from services.queue_manager import QueueManager, BASELINE_QUEUE_MAP, BASELINE_NAME_TO_ID


@pytest.fixture
def queue_manager():
    """Provides a fresh instance of QueueManager, sidestepping the singleton for isolated tests."""
    manager = QueueManager()
    return manager


def test_resolve_queue_id(queue_manager):
    """Test resolving mode names to queue IDs under various scenarios."""
    # Exact match from static map
    assert queue_manager.resolve_queue_id("ARAM") == 450
    assert queue_manager.resolve_queue_id("Ranked Solo/Duo") == 420

    # Case insensitivity
    assert queue_manager.resolve_queue_id("aram") == 450
    assert queue_manager.resolve_queue_id("ranked solo/duo") == 420

    # Fuzzy match
    assert queue_manager.resolve_queue_id("solo") == 420
    assert queue_manager.resolve_queue_id("flex") == 440

    # Fallback/invalid
    assert queue_manager.resolve_queue_id("") == 450
    assert queue_manager.resolve_queue_id(None) == 450
    assert queue_manager.resolve_queue_id("Unknown Mode that Does Not Exist") == 450


def test_resolve_mode_name(queue_manager):
    """Test resolving queue IDs to display mode names."""
    # Exact match
    assert queue_manager.resolve_mode_name(450) == "ARAM"
    assert queue_manager.resolve_mode_name(420) == "Ranked Solo/Duo"
    assert queue_manager.resolve_mode_name("420") == "Ranked Solo/Duo"

    # Unknown ID fallback
    assert queue_manager.resolve_mode_name(9999) == "Queue 9999"

    # Invalid input handling
    assert queue_manager.resolve_mode_name("not an int") == "ARAM"
    assert queue_manager.resolve_mode_name(None) == "ARAM"


def test_get_categorized_groups(queue_manager):
    """Ensure categorized groups match baseline if LCU is not connected/hasn't been parsed."""
    groups = queue_manager.get_categorized_groups()
    assert isinstance(groups, list)

    # We expect some known groups
    group_names = [name for name, _ in groups]
    assert "Ranked" in group_names
    assert "Casual" in group_names
    assert "ARAM" in group_names


def test_matchmaking_actions(queue_manager):
    """Verify that matchmaking action delegates correctly hit LCU request methods."""
    lcu = MagicMock()
    lcu.is_connected = True

    # Test start_matchmaking success
    lcu.request.return_value = MagicMock(status_code=200)
    assert queue_manager.start_matchmaking(lcu) is True
    lcu.request.assert_called_with("POST", "/lol-lobby/v2/lobby/matchmaking/search")

    # Test stop_matchmaking success
    lcu.request.return_value = MagicMock(status_code=204)
    assert queue_manager.stop_matchmaking(lcu) is True
    lcu.request.assert_called_with("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")

    # Test create_lobby success
    lcu.request.return_value = MagicMock(status_code=200)
    assert queue_manager.create_lobby(lcu, 450) is True
    lcu.request.assert_called_with("POST", "/lol-lobby/v2/lobby", {"queueId": 450})

    # Test failure case (bad status code)
    lcu.request.return_value = MagicMock(status_code=400)
    assert queue_manager.start_matchmaking(lcu) is False


def test_matchmaking_actions_not_connected(queue_manager):
    """Ensure matchmaking methods safely abort if no valid LCU object is passed."""
    lcu = MagicMock()
    lcu.is_connected = False
    assert queue_manager.start_matchmaking(lcu) is False
    assert queue_manager.stop_matchmaking(lcu) is False
    assert queue_manager.create_lobby(lcu, 450) is False
    assert queue_manager.start_matchmaking(None) is False


def test_update_available_lobby_types(queue_manager):
    """Simulate a dynamic queue update and verify it handles categorization."""
    lcu = MagicMock()
    lcu.is_connected = True

    # Setup mock JSON response mimicking an LCU /lol-game-queues/v1/queues response
    # We'll provide two available queues and one custom queue to ensure filtering
    queues_payload = [
        {
            "id": 1111,
            "name": "Super Ultra Fast Test Mode",
            "queueAvailability": "Available",
            "isCustom": False,
            "category": "PvP",
            "gameMode": "CLASSIC",
            "isRanked": False,
        },
        {
            "id": 2222,
            "name": "Super Ranked Test Mode",
            "queueAvailability": "Available",
            "isCustom": False,
            "category": "PvP",
            "gameMode": "CLASSIC",
            "isRanked": True,
        },
        {
            "id": 3333,
            "name": "Custom Test Mode",
            "queueAvailability": "Available",
            "isCustom": True,  # should be ignored
        },
        {
            "id": 4444,
            "name": "Disabled Mode",
            "queueAvailability": "Disabled", # should be ignored
            "isCustom": False,
        }
    ]

    lcu_res = MagicMock(status_code=200)
    lcu_res.json.return_value = queues_payload
    lcu.request.return_value = lcu_res

    groups = queue_manager.update_available_lobby_types(lcu)

    # Verify mapping updated
    assert queue_manager.resolve_queue_id("Super Ultra Fast Test Mode") == 1111
    assert queue_manager.resolve_queue_id("Super Ranked Test Mode") == 2222
    assert queue_manager.resolve_mode_name(1111) == "Super Ultra Fast Test Mode"

    # Ensure custom/disabled queues were NOT added
    assert queue_manager.resolve_mode_name(3333) == "Queue 3333"
    assert queue_manager.resolve_mode_name(4444) == "Queue 4444"

    # Check categorization groups for the new queues
    group_names = [name for name, _ in groups]
    assert "Casual" in group_names
    assert "Ranked" in group_names

    # Validate items within groups based on the payload above
    casual_items = next((items for name, items in groups if name == "Casual"), [])
    ranked_items = next((items for name, items in groups if name == "Ranked"), [])

    assert "Super Ultra Fast Test Mode" in casual_items
    assert "Super Ranked Test Mode" in ranked_items
