"""
Unit tests for QueueManager service.
"""

from services.queue_manager import (
    QueueManager,
    get_categorized_lobby_types,
    resolve_mode_name,
    resolve_queue_id,
    update_available_lobby_types,
)


class MockLCU:
    def __init__(self, queues_data=None, is_connected=True):
        self.is_connected = is_connected
        self._queues_data = queues_data or [
            {
                "id": 420,
                "name": "Ranked Solo/Duo",
                "queueAvailability": "Available",
                "isCustom": False,
                "isRanked": True,
                "category": "PvP",
                "gameMode": "CLASSIC",
            },
            {
                "id": 450,
                "name": "ARAM",
                "queueAvailability": "Available",
                "isCustom": False,
                "isRanked": False,
                "category": "PvP",
                "gameMode": "ARAM",
            },
            {
                "id": 2400,
                "name": "ARAM: Mayhem",
                "queueAvailability": "Available",
                "isCustom": False,
                "isRanked": False,
                "category": "PvP",
                "gameMode": "KIWI",
            },
            {
                "id": 1750,
                "name": "Arena 3x6",
                "queueAvailability": "Available",
                "isCustom": False,
                "isRanked": False,
                "category": "PvP",
                "gameMode": "CHERRY",
            },
        ]

    def request(self, method, endpoint, silent=False):
        class MockResponse:
            def __init__(self, json_data, status_code=200):
                self._json = json_data
                self.status_code = status_code

            def json(self):
                return self._json

        if endpoint == "/lol-game-queues/v1/queues":
            return MockResponse(self._queues_data)
        return MockResponse({}, status_code=404)


def test_queue_manager_resolvers():
    assert resolve_queue_id("ARAM") == 450
    assert resolve_queue_id("Ranked Solo/Duo") == 420
    assert resolve_mode_name(450) == "ARAM"
    assert resolve_mode_name(420) == "Ranked Solo/Duo"
    assert resolve_mode_name(2400) == "ARAM Mayhem"


def test_dynamic_update_from_lcu():
    mock_lcu = MockLCU()
    groups = update_available_lobby_types(mock_lcu)

    assert len(groups) > 0
    # Verify exact rotating gamemode "ARAM: Mayhem" and "Arena 3x6" resolved
    assert resolve_mode_name(2400, mock_lcu) == "ARAM: Mayhem"
    assert resolve_mode_name(1750, mock_lcu) == "Arena 3x6"
    assert resolve_queue_id("ARAM: Mayhem", mock_lcu) == 2400
