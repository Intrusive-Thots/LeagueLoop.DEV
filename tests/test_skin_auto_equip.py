import unittest
from unittest.mock import MagicMock

from services.automation.champ_select import equip_random_skin


class TestSkinAutoEquip(unittest.TestCase):

    def setUp(self):
        self.engine_mock = MagicMock()
        self.engine_mock._get_local_player.return_value = {
            "cellId": 1,
            "championId": 103,  # Ahri
        }
        self.engine_mock.lcu = MagicMock()
        self.engine_mock._skin_equipped = False

    def test_equip_random_skin_selects_custom_owned_skin(self):
        mock_skins = [
            {"id": 103000, "isBase": True, "name": "Ahri", "ownership": {"owned": True}},
            {"id": 103001, "isBase": False, "name": "Dynasty Ahri", "ownership": {"owned": True}},
        ]
        res_mock = MagicMock()
        res_mock.status_code = 200
        res_mock.json.return_value = mock_skins
        self.engine_mock.lcu.request.return_value = res_mock

        equip_random_skin(self.engine_mock, {"myTeam": [{"cellId": 1, "championId": 103}], "localPlayerCellId": 1})

        self.assertTrue(self.engine_mock._skin_equipped)
        self.engine_mock.lcu.request.assert_called_with(
            "PATCH",
            "/lol-champ-select/v1/session/my-selection",
            data={"selectedSkinId": 103001}
        )

    def test_equip_random_skin_fallback_to_unlocked(self):
        mock_skins = [
            {"id": 103000, "isBase": True, "name": "Ahri", "unlocked": True},
        ]
        res_mock = MagicMock()
        res_mock.status_code = 200
        res_mock.json.return_value = mock_skins
        self.engine_mock.lcu.request.return_value = res_mock

        equip_random_skin(self.engine_mock, {"myTeam": [{"cellId": 1, "championId": 103}], "localPlayerCellId": 1})

        self.assertTrue(self.engine_mock._skin_equipped)


if __name__ == "__main__":
    unittest.main()
