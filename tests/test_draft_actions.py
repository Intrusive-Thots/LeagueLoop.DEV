"""
Champ select actions.

The draft screen could not pick, ban or hover: `pick_requested` was emitted
and connected to nothing. These tests cover the action-resolution logic,
which is the part that decides *which* LCU action id to PATCH — getting it
wrong means overwriting a ban you already made, or a pick from a previous
phase.
"""
import unittest

from services.draft_actions import (
    DraftActions,
    DraftError,
    current_action,
    parse_actions,
)

# Cell 2 is us. We have banned already; our pick is in progress.
SESSION = {
    "localPlayerCellId": 2,
    "actions": [
        [
            {"id": 10, "actorCellId": 2, "type": "ban",
             "completed": True, "isInProgress": False, "championId": 51},
            {"id": 11, "actorCellId": 7, "type": "ban",
             "completed": True, "isInProgress": False},
        ],
        [
            {"id": 20, "actorCellId": 0, "type": "pick",
             "completed": True, "isInProgress": False, "championId": 86},
            {"id": 21, "actorCellId": 2, "type": "pick",
             "completed": False, "isInProgress": True, "championId": 0},
        ],
    ],
}


class FakeResponse:
    def __init__(self, status_code=204, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeLcu:
    def __init__(self, session=SESSION, patch_status=204, connected=True,
                 patch_payload=None):
        self.is_connected = connected
        self.session = session
        self.patch_status = patch_status
        self.patch_payload = patch_payload
        self.calls = []

    def request(self, method, endpoint, data=None, silent=False):
        self.calls.append((method, endpoint, data))
        if method == "GET":
            return FakeResponse(200, self.session) if self.session else FakeResponse(404)
        return FakeResponse(self.patch_status, self.patch_payload)


class ParsingTests(unittest.TestCase):
    def test_action_groups_are_flattened(self):
        self.assertEqual([a.id for a in parse_actions(SESSION)], [10, 11, 20, 21])

    def test_malformed_actions_are_skipped_not_fatal(self):
        session = {"actions": [[{"id": "nope"}, None, {"id": 5, "actorCellId": 1}]]}
        ids = [a.id for a in parse_actions(session)]
        self.assertEqual(ids, [5])

    def test_no_actions(self):
        self.assertEqual(parse_actions({}), [])


class CurrentActionTests(unittest.TestCase):
    def test_picks_the_in_progress_action_that_is_mine(self):
        action = current_action(SESSION)
        self.assertIsNotNone(action)
        self.assertEqual(action.id, 21)
        self.assertTrue(action.is_pick)

    def test_does_not_return_my_completed_ban(self):
        """Taking the first action with my cell id would PATCH the ban."""
        action = current_action(SESSION)
        self.assertNotEqual(action.id, 10)

    def test_does_not_return_someone_elses_turn(self):
        session = dict(SESSION)
        session["actions"] = [[{"id": 30, "actorCellId": 9, "type": "pick",
                                "isInProgress": True, "completed": False}]]
        self.assertIsNone(current_action(session))

    def test_no_cell_id_means_no_action(self):
        self.assertIsNone(current_action({"actions": []}))
        self.assertIsNone(current_action({"localPlayerCellId": -1}))


class PickTests(unittest.TestCase):
    def test_hover_patches_without_completing(self):
        lcu = FakeLcu()
        result = DraftActions(lcu).hover(103)
        self.assertTrue(result.ok)
        method, endpoint, body = lcu.calls[-1]
        self.assertEqual(method, "PATCH")
        self.assertTrue(endpoint.endswith("/actions/21"))
        self.assertEqual(body, {"championId": 103})

    def test_lock_in_sets_completed(self):
        lcu = FakeLcu()
        result = DraftActions(lcu).lock_in(103)
        self.assertTrue(result.ok)
        _method, _endpoint, body = lcu.calls[-1]
        self.assertEqual(body, {"championId": 103, "completed": True})

    def test_a_disconnected_client_is_reported_not_attempted(self):
        lcu = FakeLcu(connected=False)
        result = DraftActions(lcu).lock_in(103)
        self.assertFalse(result.ok)
        self.assertIs(result.error, DraftError.NOT_CONNECTED)
        self.assertEqual(lcu.calls, [])

    def test_outside_champ_select_is_its_own_message(self):
        result = DraftActions(FakeLcu(session=None)).lock_in(103)
        self.assertIs(result.error, DraftError.NO_SESSION)
        self.assertIn("champion select", result.message.lower())

    def test_not_your_turn(self):
        session = {"localPlayerCellId": 2, "actions": [
            [{"id": 40, "actorCellId": 0, "type": "pick",
              "isInProgress": True, "completed": False}]]}
        result = DraftActions(FakeLcu(session=session)).lock_in(103)
        self.assertIs(result.error, DraftError.NOT_YOUR_TURN)

    def test_already_locked_is_distinct_from_not_your_turn(self):
        session = {"localPlayerCellId": 2, "actions": [
            [{"id": 41, "actorCellId": 2, "type": "pick",
              "isInProgress": False, "completed": True, "championId": 103}]]}
        result = DraftActions(FakeLcu(session=session)).lock_in(103)
        self.assertIs(result.error, DraftError.ALREADY_LOCKED)
        self.assertIn("already", result.message.lower())

    def test_a_refusal_surfaces_the_clients_own_reason(self):
        lcu = FakeLcu(patch_status=400,
                      patch_payload={"message": "Champion not owned"})
        result = DraftActions(lcu).lock_in(103)
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "Champion not owned")

    def test_a_refusal_without_a_body_still_says_something(self):
        result = DraftActions(FakeLcu(patch_status=500)).lock_in(103)
        self.assertFalse(result.ok)
        self.assertTrue(result.message)


class QueryTests(unittest.TestCase):
    def test_can_act_reflects_the_session(self):
        self.assertTrue(DraftActions(FakeLcu()).can_act())
        self.assertFalse(DraftActions(FakeLcu(session=None)).can_act())

    def test_pending_type_lets_the_ui_label_itself(self):
        self.assertEqual(DraftActions(FakeLcu()).pending_type(), "pick")
        self.assertEqual(DraftActions(FakeLcu(session=None)).pending_type(), "")


if __name__ == "__main__":
    unittest.main()
