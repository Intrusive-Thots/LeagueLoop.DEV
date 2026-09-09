import unittest

from services.queue_manager import (
    QueueManager,
    update_available_lobby_types,
    get_categorized_lobby_types,
    resolve_queue_id,
    resolve_mode_name,
    start_matchmaking,
    stop_matchmaking,
    create_lobby,
)

class FakeResponse:
    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload

class FakeLcu:
    def __init__(self, connected=True, queues=None, post_status=200, delete_status=200):
        self.is_connected = connected
        self.queues = queues
        self.post_status = post_status
        self.delete_status = delete_status

    def request(self, method, endpoint, silent=False, data=None):
        if method == "GET" and endpoint == "/lol-game-queues/v1/queues":
            if self.queues is None:
                return FakeResponse(None, 404)
            return FakeResponse(self.queues, 200)
        if method == "POST":
            return FakeResponse(None, self.post_status)
        if method == "DELETE":
            return FakeResponse(None, self.delete_status)
        return FakeResponse(None, 404)


class QueueManagerTests(unittest.TestCase):
    def setUp(self):
        # We need a fresh QueueManager per test so state changes don't leak
        self.qm = QueueManager()

    def test_resolve_queue_id_baseline(self):
        self.assertEqual(self.qm.resolve_queue_id("ARAM"), 450)
        self.assertEqual(self.qm.resolve_queue_id("Ranked Solo/Duo"), 420)

    def test_resolve_queue_id_case_insensitive(self):
        self.assertEqual(self.qm.resolve_queue_id("aram"), 450)
        self.assertEqual(self.qm.resolve_queue_id("ranked solo/duo"), 420)

    def test_resolve_queue_id_fuzzy(self):
        # 'Ranked Solo' is in BASELINE_NAME_TO_ID
        self.assertEqual(self.qm.resolve_queue_id("Ranked Solo"), 420)
        # Random substring if it doesn't match keys exactly might fallback to fuzzy matching
        self.assertEqual(self.qm.resolve_queue_id("Draft"), 400)

    def test_resolve_queue_id_default_empty(self):
        self.assertEqual(self.qm.resolve_queue_id(None), 450)
        self.assertEqual(self.qm.resolve_queue_id(""), 450)

    def test_resolve_queue_id_unknown(self):
        self.assertEqual(self.qm.resolve_queue_id("CompletelyUnknownMode"), 450) # Fallback is 450

    def test_resolve_mode_name(self):
        self.assertEqual(self.qm.resolve_mode_name(450), "ARAM")
        self.assertEqual(self.qm.resolve_mode_name("420"), "Ranked Solo/Duo")

    def test_resolve_mode_name_invalid_types(self):
        self.assertEqual(self.qm.resolve_mode_name(None), "ARAM")
        self.assertEqual(self.qm.resolve_mode_name("NotAnInt"), "ARAM")

    def test_resolve_mode_name_unknown(self):
        self.assertEqual(self.qm.resolve_mode_name(99999), "Queue 99999")

    def test_update_available_lobby_types_no_lcu(self):
        groups = self.qm.update_available_lobby_types(None)
        # Should return default groups
        self.assertTrue(len(groups) > 0)
        self.assertEqual(groups, self.qm.get_categorized_groups())

    def test_update_available_lobby_types_disconnected(self):
        groups = self.qm.update_available_lobby_types(FakeLcu(connected=False))
        self.assertEqual(groups, self.qm.get_categorized_groups())

    def test_update_available_lobby_types_success(self):
        queues = [
            {
                "id": 999,
                "name": "Super Custom Queue",
                "queueAvailability": "Available",
                "isCustom": False,
                "category": "PvP",
                "gameMode": "CLASSIC",
            },
            {
                "id": 888,
                "name": "Ranked New",
                "queueAvailability": "Available",
                "isCustom": False,
                "category": "PvP",
                "gameMode": "CLASSIC",
                "isRanked": True
            }
        ]
        groups = self.qm.update_available_lobby_types(FakeLcu(queues=queues))

        # Super Custom Queue -> Casual
        # Ranked New -> Ranked
        categories = dict(groups)
        self.assertIn("Casual", categories)
        self.assertIn("Ranked", categories)
        self.assertIn("Super Custom Queue", categories["Casual"])
        self.assertIn("Ranked New", categories["Ranked"])

        # Also mapping should be updated
        self.assertEqual(self.qm.resolve_queue_id("Super Custom Queue"), 999)
        self.assertEqual(self.qm.resolve_mode_name(999), "Super Custom Queue")

    def test_matchmaking_actions(self):
        lcu = FakeLcu(post_status=204, delete_status=204)
        self.assertTrue(self.qm.start_matchmaking(lcu))
        self.assertTrue(self.qm.stop_matchmaking(lcu))
        self.assertTrue(self.qm.create_lobby(lcu, 450))

        bad_lcu = FakeLcu(post_status=500, delete_status=404)
        self.assertFalse(self.qm.start_matchmaking(bad_lcu))
        self.assertFalse(self.qm.stop_matchmaking(bad_lcu))
        self.assertFalse(self.qm.create_lobby(bad_lcu, 450))

        self.assertFalse(self.qm.start_matchmaking(None))

class QueueManagerGlobalHelperTests(unittest.TestCase):
    def test_globals_forward_to_instance(self):
        self.assertEqual(resolve_queue_id("ARAM"), 450)
        self.assertEqual(resolve_mode_name(450), "ARAM")
        self.assertTrue(len(get_categorized_lobby_types()) > 0)

        lcu = FakeLcu(post_status=204, delete_status=204)
        self.assertTrue(start_matchmaking(lcu))
        self.assertTrue(stop_matchmaking(lcu))
        self.assertTrue(create_lobby(lcu, 450))

if __name__ == "__main__":
    unittest.main()
