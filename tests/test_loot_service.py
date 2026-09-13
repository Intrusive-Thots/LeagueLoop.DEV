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

    def test_claim_season_pass_rewards_success(self):
        def mock_request(method, endpoint, data=None, silent=False):
            if method == "GET" and endpoint == "/lol-event-hub/v1/events":
                return DummyResponse(200, [{"id": "event_pass_2026", "name": "Noxus Event Pass"}])
            if method == "GET" and "/reward-track/unclaimed-rewards" in endpoint:
                return DummyResponse(200, {"rewardsCount": 4})
            if method == "POST" and "/lol-event-hub/v1/events/event_pass_2026/reward-track/claim-all" in endpoint:
                return DummyResponse(204, {})
            return DummyResponse(404, {})

        self.mock_lcu.request.side_effect = mock_request
        res = self.service.claim_season_pass_rewards()
        self.assertEqual(res.claimed, 4)
        self.assertIn("Season/Event Pass (Noxus Event Pass)", res.sources)
        self.assertTrue(any("Claimed 4 reward(s) from Season/Event Pass" in log for log in self.logs))

    def test_claim_season_progression_grants_success(self):
        def mock_request(method, endpoint, data=None, silent=False):
            if method == "GET" and endpoint == "/lol-rewards/v1/grants":
                return DummyResponse(200, [
                    {
                        "info": {
                            "id": "grant_999",
                            "rewardGroupId": "group_888",
                            "status": "PENDING_SELECTION",
                        },
                        "rewardGroup": {
                            "rewards": [
                                {
                                    "id": "reward_choice_1",
                                    "localizations": {"title": "750 Blue Essence"},
                                }
                            ]
                        },
                    }
                ])
            if method == "POST" and endpoint == "/lol-rewards/v1/grants/grant_999/select":
                self.assertEqual(data.get("grantId"), "grant_999")
                self.assertEqual(data.get("rewardGroupId"), "group_888")
                self.assertEqual(data.get("selections"), ["reward_choice_1"])
                return DummyResponse(200, {})
            return DummyResponse(404, {})

        self.mock_lcu.request.side_effect = mock_request
        res = self.service.claim_season_progression_grants()
        self.assertEqual(res.claimed, 1)
        self.assertIn("Progression: 750 Blue Essence", res.sources)
        self.assertTrue(any("Claimed progression reward: 750 Blue Essence" in log for log in self.logs))

    def test_claim_tft_pass_rewards_success(self):
        def mock_request(method, endpoint, data=None, silent=False):
            if method == "GET" and endpoint == "/lol-tft-pass/v1/active-passes":
                return DummyResponse(200, [
                    {
                        "info": {
                            "passId": "tft_pass_set13",
                            "title": "Into the Arcane Pass",
                        }
                    }
                ])
            if method == "PUT" and endpoint == "/lol-tft-pass/v1/pass/tft_pass_set13/milestone/claimAllRewards":
                return DummyResponse(200, {})
            return DummyResponse(404, {})

        self.mock_lcu.request.side_effect = mock_request
        res = self.service.claim_tft_pass_rewards()
        self.assertEqual(res.claimed, 1)
        self.assertIn("TFT Pass (Into the Arcane Pass)", res.sources)
        self.assertTrue(any("Claimed rewards from Into the Arcane Pass" in log for log in self.logs))

    def test_claim_ranked_split_rewards_success(self):
        def mock_request(method, endpoint, data=None, silent=False):
            if method == "POST" and endpoint == "/lol-ranked/v1/split-rewards/claim":
                return DummyResponse(200, {})
            if method == "POST" and endpoint == "/lol-ranked/v1/rewards/claim":
                return DummyResponse(200, {})
            return DummyResponse(404, {})

        self.mock_lcu.request.side_effect = mock_request
        res = self.service.claim_ranked_split_rewards()
        self.assertEqual(res.claimed, 2)
        self.assertIn("Ranked Split Rewards", res.sources)
        self.assertIn("Ranked Rewards", res.sources)

    def test_claim_all_rewards_pipeline(self):
        def mock_request(method, endpoint, data=None, silent=False):
            if method == "GET" and endpoint == "/lol-event-hub/v1/events":
                return DummyResponse(200, [{"id": "ev1", "name": "Event1"}])
            if method == "GET" and "/lol-event-hub/v1/events/ev1/reward-track/unclaimed-rewards" in endpoint:
                return DummyResponse(200, {"rewardsCount": 3})
            if method == "POST" and "/lol-event-hub/v1/events/ev1/reward-track/claim-all" in endpoint:
                return DummyResponse(204, {})
            if method == "GET" and endpoint == "/lol-rewards/v1/grants":
                return DummyResponse(200, [])
            if method == "GET" and endpoint == "/lol-tft-pass/v1/active-passes":
                return DummyResponse(200, [])
            if method == "POST" and "/lol-battle-pass/v1/rewards/claim" in endpoint:
                return DummyResponse(200, {"rewards": ["token_1"]})
            if method == "GET" and "/lol-missions/v1/missions" in endpoint:
                return DummyResponse(200, [{"id": "m1", "title": "M1", "status": "COMPLETED", "rewardStatus": "UNCLAIMED"}])
            if method == "POST" and "/lol-missions/v1/missions/m1/claim" in endpoint:
                return DummyResponse(200, {})
            return DummyResponse(404, {})

        self.mock_lcu.request.side_effect = mock_request
        res = self.service.claim_all_rewards()
        self.assertEqual(res.claimed, 5)  # 3 from Event Hub + 1 from legacy + 1 from mission
        self.assertTrue(any("Claim step completed: 5 reward(s)" in log for log in self.logs))

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
