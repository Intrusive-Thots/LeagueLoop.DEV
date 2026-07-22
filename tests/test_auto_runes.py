import unittest
from unittest.mock import MagicMock

from services.automation.champ_select import auto_equip_runes


class TestAutoRunes(unittest.TestCase):

    def setUp(self):
        self.engine_mock = MagicMock()
        self.engine_mock._get_local_player.return_value = {
            "cellId": 1,
            "championId": 103,  # Ahri
            "assignedPosition": "MIDDLE",
        }
        self.engine_mock.config.get.side_effect = lambda k, d=None: True
        self.engine_mock.lcu = MagicMock()
        self.engine_mock._runes_equipped = False

    def test_auto_equip_runes_recommended_page_success(self):
        rec_page_mock = MagicMock()
        rec_page_mock.status_code = 200
        rec_page_mock.json.return_value = [{"id": 9999, "name": "Ahri High Winrate"}]

        apply_mock = MagicMock()
        apply_mock.status_code = 200

        self.engine_mock.lcu.request.side_effect = [rec_page_mock, apply_mock]

        auto_equip_runes(self.engine_mock, {"myTeam": [{"cellId": 1, "championId": 103}], "localPlayerCellId": 1})

        self.assertTrue(self.engine_mock._runes_equipped)

    def test_auto_equip_runes_fallback_current_page(self):
        rec_page_mock = MagicMock()
        rec_page_mock.status_code = 404

        curr_page_mock = MagicMock()
        curr_page_mock.status_code = 200
        curr_page_mock.json.return_value = {"id": 12, "name": "Standard Page"}

        put_mock = MagicMock()
        put_mock.status_code = 200

        self.engine_mock.lcu.request.side_effect = [rec_page_mock, curr_page_mock, put_mock]

        auto_equip_runes(self.engine_mock, {"myTeam": [{"cellId": 1, "championId": 103}], "localPlayerCellId": 1})

        self.assertTrue(self.engine_mock._runes_equipped)


if __name__ == "__main__":
    unittest.main()
