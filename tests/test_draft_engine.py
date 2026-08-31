import unittest
from unittest.mock import MagicMock

from services.draft.role_detector import RoleDetector
from services.draft.validation import ActionValidator
from services.draft.priority_engine import PriorityEngine


class TestDraftSubsystem(unittest.TestCase):
    def test_role_detector_normalizes_and_extracts(self):
        self.assertEqual(RoleDetector.normalize_role("top"), "TOP")
        self.assertEqual(RoleDetector.normalize_role("mid"), "MIDDLE")
        self.assertEqual(RoleDetector.normalize_role("supp"), "UTILITY")

        session = {
            "localPlayerCellId": 2,
            "myTeam": [
                {"cellId": 0, "assignedPosition": "top"},
                {"cellId": 1, "assignedPosition": "jungle"},
                {"cellId": 2, "assignedPosition": "middle"},
            ]
        }
        self.assertEqual(RoleDetector.detect_role_from_session(session), "MIDDLE")

    def test_action_validator_banned_and_picked(self):
        session = {
            "bans": {"myTeamBans": [103], "theirTeamBans": [266]},
            "myTeam": [{"cellId": 0, "championId": 1}],
            "theirTeam": [{"cellId": 5, "championId": 2}],
            "actions": [
                [{"type": "ban", "championId": 51, "completed": True}],
                [{"type": "pick", "championId": 81, "completed": True}],
            ]
        }

        # Ahri (103), Aatrox (266), Caitlyn (51) are banned
        self.assertFalse(ActionValidator.is_champion_available(103, session, is_pick=True))
        self.assertFalse(ActionValidator.is_champion_available(266, session, is_pick=True))
        self.assertFalse(ActionValidator.is_champion_available(51, session, is_pick=True))

        # Annie (1), Olaf (2), Ezreal (81) are picked
        self.assertFalse(ActionValidator.is_champion_available(1, session, is_pick=True))
        self.assertFalse(ActionValidator.is_champion_available(81, session, is_pick=True))

        # Jinx (222) is available
        self.assertTrue(ActionValidator.is_champion_available(222, session, is_pick=True))
        # Annie is available to BAN (not banned yet)
        self.assertTrue(ActionValidator.is_champion_available(1, session, is_pick=False))

    def test_priority_engine_evaluates_pick_cascade(self):
        config = MagicMock()
        # User wants Ahri (103), then Annie (1), then Jinx (222) for MIDDLE
        config.get.side_effect = lambda key, default=None: {
            "priority_MIDDLE": [103, 1, 222],
        }.get(key, default)

        engine = PriorityEngine(config_manager=config)

        # Ahri (103) is banned, Annie (1) is already picked by enemy
        session = {
            "localPlayerCellId": 0,
            "myTeam": [{"cellId": 0, "assignedPosition": "middle"}],
            "bans": {"myTeamBans": [103], "theirTeamBans": []},
            "theirTeam": [{"cellId": 5, "championId": 1}],
            "actions": [],
        }

        decision = engine.evaluate_pick(session)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.champion_id, 222)  # Jinx chosen as fallback #3
        self.assertTrue(decision.is_fallback)
        self.assertEqual(decision.role, "MIDDLE")


    def test_priority_engine_with_champion_names_and_rejected_ids(self):
        config = MagicMock()
        config.get.side_effect = lambda key, default=None: {
            "priority_list": ["TwistedFate", "Karthus", "Sion"],
        }.get(key, default)

        assets = MagicMock()
        assets.name_to_id.side_effect = lambda name: {"TwistedFate": 4, "Karthus": 30, "Sion": 14}.get(name, 0)
        assets.get_champ_roles.return_value = []

        engine = PriorityEngine(config_manager=config, asset_manager=assets)

        session = {
            "localPlayerCellId": 0,
            "myTeam": [{"cellId": 0, "assignedPosition": ""}],
            "bans": {"myTeamBans": [], "theirTeamBans": []},
            "theirTeam": [],
            "actions": [],
        }

        # Normal pick -> TF (4)
        decision = engine.evaluate_pick(session)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.champion_id, 4)

        # If TF was rejected by client (e.g. not owned), engine picks Karthus (30)
        decision2 = engine.evaluate_pick(session, rejected_ids={4})
        self.assertIsNotNone(decision2)
        self.assertEqual(decision2.champion_id, 30)

    def test_priority_engine_falls_back_to_legacy_priority_picker(self):
        config = MagicMock()
        config.get.side_effect = lambda key, default=None: {
            "priority_list": [],
            "priority_picker": {"enabled": True, "list": ["Amumu", "Ashe"]},
        }.get(key, default)

        assets = MagicMock()
        assets.name_to_id.side_effect = lambda name: {"Amumu": 32, "Ashe": 22}.get(name, 0)
        assets.get_champ_roles.return_value = []

        engine = PriorityEngine(config_manager=config, asset_manager=assets)

        session = {
            "localPlayerCellId": 0,
            "myTeam": [{"cellId": 0, "assignedPosition": ""}],
            "bans": {"myTeamBans": [], "theirTeamBans": []},
            "theirTeam": [],
            "actions": [],
        }

        decision = engine.evaluate_pick(session)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.champion_id, 32)


if __name__ == "__main__":
    unittest.main()

