"""
Tests for ARAM Champion Select live highlighting on the Champion Priority List.
"""
import unittest
from unittest.mock import MagicMock, patch

from ui.components.priority_grid import PriorityIconGrid
from ui.components.aram_list_window import AramListWindow


class TestAramChampSelectHighlights(unittest.TestCase):
    def setUp(self):
        AramListWindow._last_aram_champ_select_state = None
        AramListWindow._instance = None

    def tearDown(self):
        AramListWindow._last_aram_champ_select_state = None
        AramListWindow._instance = None

    def test_norm_name(self):
        self.assertEqual(PriorityIconGrid._norm_name("Dr. Mundo"), "drmundo")
        self.assertEqual(PriorityIconGrid._norm_name("Cho'Gath"), "chogath")
        self.assertEqual(PriorityIconGrid._norm_name("K'Sante"), "ksante")
        self.assertEqual(PriorityIconGrid._norm_name("Miss Fortune"), "missfortune")
        self.assertEqual(PriorityIconGrid._norm_name("Jinx"), "jinx")
        self.assertEqual(PriorityIconGrid._norm_name(""), "")
        self.assertEqual(PriorityIconGrid._norm_name(None), "")

    def test_highlight_info_classification(self):
        grid = MagicMock(spec=PriorityIconGrid)
        grid.list_kind = "aram"
        grid._norm_name = PriorityIconGrid._norm_name
        grid._get_champ_highlight_info = PriorityIconGrid._get_champ_highlight_info.__get__(grid)

        grid._aram_my_name = "jinx"
        grid._aram_bench_names = {"poppy", "teemo"}
        grid._aram_team_names = {"caitlyn", "lux"}

        # Local player check
        me_info = grid._get_champ_highlight_info("Jinx")
        self.assertIsNotNone(me_info)
        self.assertEqual(me_info[0], "me")
        self.assertEqual(me_info[1], "#00FF88")  # Green border
        self.assertEqual(me_info[3], "YOU")      # Badge text
        self.assertIn("Selected by You", me_info[6])

        # Bench champion check
        bench_info = grid._get_champ_highlight_info("Poppy")
        self.assertIsNotNone(bench_info)
        self.assertEqual(bench_info[0], "bench")
        self.assertEqual(bench_info[1], "#00D4FF")  # Cyan border
        self.assertEqual(bench_info[3], "BENCH")    # Badge text
        self.assertIn("Available on Bench", bench_info[6])

        # Teammate pick check
        team_info = grid._get_champ_highlight_info("Caitlyn")
        self.assertIsNotNone(team_info)
        self.assertEqual(team_info[0], "team")
        self.assertEqual(team_info[1], "#FFC107")  # Amber/Gold border
        self.assertEqual(team_info[3], "TEAM")     # Badge text
        self.assertIn("Selected by Teammate", team_info[6])

        # Unselected champion check
        other_info = grid._get_champ_highlight_info("Yasuo")
        self.assertIsNone(other_info)

    def test_ban_list_does_not_apply_aram_highlights(self):
        grid = MagicMock(spec=PriorityIconGrid)
        grid.list_kind = "ban"
        grid._norm_name = PriorityIconGrid._norm_name
        grid._get_champ_highlight_info = PriorityIconGrid._get_champ_highlight_info.__get__(grid)

        grid._aram_my_name = "jinx"
        grid._aram_bench_names = {"poppy"}
        grid._aram_team_names = {"caitlyn"}

        self.assertIsNone(grid._get_champ_highlight_info("Jinx"))
        self.assertIsNone(grid._get_champ_highlight_info("Poppy"))
        self.assertIsNone(grid._get_champ_highlight_info("Caitlyn"))

    def test_aram_list_window_state_caching_and_dispatch(self):
        # When window is not open, state is cached
        AramListWindow.update_champ_select_state(
            bench_names=["Poppy", "Teemo"],
            my_name="Jinx",
            team_names=["Caitlyn", "Lux"]
        )
        self.assertEqual(
            AramListWindow._last_aram_champ_select_state,
            {
                "bench": ["Poppy", "Teemo"],
                "me": "Jinx",
                "team": ["Caitlyn", "Lux"],
            }
        )

        # When clear is called, state is cleared
        AramListWindow.clear_champ_select_state()
        self.assertIsNone(AramListWindow._last_aram_champ_select_state)

        # When window is open, update calls _apply_live_champ_select_state
        mock_win = MagicMock()
        mock_win.winfo_exists.return_value = True
        AramListWindow._instance = mock_win

        AramListWindow.update_champ_select_state(
            bench_names=["Aatrox"],
            my_name="Ahri",
            team_names=["Akali"]
        )
        mock_win._apply_live_champ_select_state.assert_called_once()

        AramListWindow.clear_champ_select_state()
        mock_win._clear_live_champ_select_state.assert_called_once()

    def test_update_lobby_stats_forwards_aram_state(self):
        from ui.app_sidebar import SidebarWidget
        sidebar = MagicMock(spec=SidebarWidget)
        sidebar.winfo_exists.return_value = True
        sidebar.assets = MagicMock()
        sidebar.assets.get_champ_name.side_effect = lambda cid: {
            1: "Annie", 222: "Jinx", 78: "Poppy", 51: "Caitlyn"
        }.get(cid, str(cid))
        sidebar.scraper = None
        sidebar.update_lobby_stats = SidebarWidget.update_lobby_stats.__get__(sidebar)

        team = [
            {"cellId": 0, "championId": 222},  # Me (Jinx)
            {"cellId": 1, "championId": 51},   # Teammate (Caitlyn)
        ]
        bench = [{"championId": 78}]           # Poppy
        me = {"cellId": 0, "championId": 222}
        session = {
            "queueId": 450,
            "benchEnabled": True,
            "gameConfig": {"gameMode": "ARAM"},
        }

        with patch.object(AramListWindow, "update_champ_select_state") as mock_update:
            sidebar.update_lobby_stats(team, bench, me=me, session=session)
            mock_update.assert_called_once_with(["Poppy"], "Jinx", ["Caitlyn"])

    def test_update_lobby_stats_clears_on_empty_team(self):
        from ui.app_sidebar import SidebarWidget
        sidebar = MagicMock(spec=SidebarWidget)
        sidebar.winfo_exists.return_value = True
        sidebar.assets = MagicMock()
        sidebar.scraper = None
        sidebar.update_lobby_stats = SidebarWidget.update_lobby_stats.__get__(sidebar)

        with patch.object(AramListWindow, "clear_champ_select_state") as mock_clear:
            sidebar.update_lobby_stats([], [], me=None, session=None)
            mock_clear.assert_called_once()


if __name__ == "__main__":
    unittest.main()
