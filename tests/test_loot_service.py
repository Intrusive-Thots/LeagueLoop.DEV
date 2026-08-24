"""
Unit tests for LootService and reward claiming engine.
Validates battle pass claiming, mission rewards, loot milestones, and open pipeline.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from services.loot_service import LootItem, LootService, OpenPlan, OpenResult


class DummyResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text
        self.content = b"{}" if json_data is not None else b""
        self.reason = "OK" if status_code < 400 else "Error"

    def json(self):
        if isinstance(self._json, Exception):
            raise self._json
        return self._json


class TestLootServiceClaiming(unittest.TestCase):
    def setUp(self):
        self.mock_lcu = MagicMock()
        self.mock_lcu.is_connected = True
        self.logs: list[str] = []
        self.service = LootService(self.mock_lcu, log=self.logs.append)

    def test_claim_battle_pass_rewards_success(self):
        def mock_request(method, endpoint, data=None, silent=False):
            if method == "POST" and "/lol-battle-pass/v1/rewards/claim" in endpoint:
                return DummyResponse(200, {"rewards": ["pass_reward_63", "pass_reward_64"]})
            return DummyResponse(404, {})

        self.mock_lcu.request.side_effect = mock_request
        res = self.service.claim_battle_pass_rewards()
        self.assertEqual(res.claimed, 2)
        self.assertIn("Pass (/lol-battle-pass/v1/rewards/claim)", res.sources)
        self.assertTrue(any("Successfully claimed 2" in log for log in self.logs))

    def test_claim_mission_rewards_success(self):
        def mock_request(method, endpoint, data=None, silent=False):
            if method == "GET" and "/lol-missions/v1/missions" in endpoint:
                return DummyResponse(200, [
                    {"id": "mission_101", "title": "Play 3 Games", "status": "COMPLETED", "rewardStatus": "UNCLAIMED"},
                    {"id": "mission_102", "title": "Score 20 Takedowns", "status": "IN_PROGRESS", "rewardStatus": "LOCKED"},
                ])
            if method == "POST" and "/lol-missions/v1/missions/mission_101/claim" in endpoint:
                return DummyResponse(200, {"status": "SUCCESS"})
            return DummyResponse(404, {})

        self.mock_lcu.request.side_effect = mock_request
        res = self.service.claim_mission_rewards()
        self.assertEqual(res.claimed, 1)
        self.assertIn("Mission: Play 3 Games", res.sources)

    def test_claim_loot_milestones_success(self):
        def mock_request(method, endpoint, data=None, silent=False):
            if method == "GET" and "/lol-loot/v1/milestones" in endpoint:
                return DummyResponse(200, [
                    {
                        "milestones": [
                            {"id": "ms_5", "status": "COMPLETED"},
                            {"id": "ms_10", "status": "IN_PROGRESS"},
                        ]
                    }
                ])
            if method == "POST" and "/lol-loot/v1/milestones/ms_5/claim" in endpoint:
                return DummyResponse(200, {"status": "SUCCESS"})
            return DummyResponse(404, {})

        self.mock_lcu.request.side_effect = mock_request
        res = self.service.claim_loot_milestones()
        self.assertEqual(res.claimed, 1)
        self.assertIn("Milestone ms_5", res.sources)

    def test_claim_mastery_and_grants(self):
        def mock_request(method, endpoint, data=None, silent=False):
            if method == "POST" and "/lol-champion-mastery/v1/milestones/claim" in endpoint:
                return DummyResponse(200, {})
            if method == "POST" and "/lol-rewards/v1/grants/claim" in endpoint:
                return DummyResponse(200, {})
            return DummyResponse(404, {})

        self.mock_lcu.request.side_effect = mock_request
        res = self.service.claim_mastery_and_grants()
        self.assertEqual(res.claimed, 2)

    def test_claim_all_rewards_pipeline(self):
        def mock_request(method, endpoint, data=None, silent=False):
            if method == "POST" and "/lol-battle-pass/v1/rewards/claim" in endpoint:
                return DummyResponse(200, {"rewards": ["token_1"]})
            if method == "GET" and "/lol-missions/v1/missions" in endpoint:
                return DummyResponse(200, [{"id": "m1", "title": "M1", "status": "COMPLETED", "rewardStatus": "UNCLAIMED"}])
            if method == "POST" and "/lol-missions/v1/missions/m1/claim" in endpoint:
                return DummyResponse(200, {})
            return DummyResponse(404, {})

        self.mock_lcu.request.side_effect = mock_request
        res = self.service.claim_all_rewards()
        self.assertEqual(res.claimed, 2)
        self.assertTrue(any("Claim step completed: 2 reward(s)" in log for log in self.logs))

    def test_open_all_with_claim_first(self):
        inventory = [{"lootId": "CHEST_champion_capsule", "localizedName": "Champion Capsule", "count": 1, "type": "CHEST", "displayCategories": "CHEST"}]

        def mock_request(method, endpoint, data=None, silent=False):
            if method == "POST" and "/lol-battle-pass/v1/rewards/claim" in endpoint:
                return DummyResponse(200, {"rewards": ["pass_capsule"]})
            if method == "GET" and "/lol-loot/v1/player-loot" in endpoint:
                return DummyResponse(200, [dict(i) for i in inventory if i["count"] > 0])
            if method == "GET" and "/lol-loot/v1/recipes/initial-item/CHEST_champion_capsule" in endpoint:
                return DummyResponse(200, [
                    {"recipeName": "CHEST_champion_capsule_OPEN", "type": "OPEN", "slots": []}
                ])
            if method == "POST" and "/lol-loot/v1/recipes/CHEST_champion_capsule_OPEN/craft" in endpoint:
                for item in inventory:
                    if item["lootId"] == "CHEST_champion_capsule":
                        item["count"] -= 1
                return DummyResponse(200, {"added": []})
            return DummyResponse(404, {})

        self.mock_lcu.request.side_effect = mock_request
        result = self.service.open_all(craft_keys_first=False, claim_rewards_first=True)
        self.assertEqual(result.rewards_claimed, 1)
        self.assertEqual(result.opened, 1)


if __name__ == "__main__":
    unittest.main()
