import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import unittest
from unittest.mock import MagicMock, patch

class DummyWidget:
    def __init__(self, *args, **kwargs):
        self._exists = True
        self.master = args[0] if len(args) > 0 else MagicMock()
        self.tk = MagicMock()
        self._w = ".dummy"
        self._last_child_ids = {}
        self.children = {}
        self._config = {"state": "normal", "fg_color": "#000000", "hover_color": "#333333"}
        self._config.update(kwargs)
        self._bindings = {}
        self._after_callbacks = []
        self._mapped = False
    def bind(self, sequence, func=None, add=None):
        if add == "+":
            if sequence not in self._bindings:
                self._bindings[sequence] = []
            self._bindings[sequence].append(func)
        else:
            self._bindings[sequence] = [func]
    def unbind(self, sequence, funcid=None):
        self._bindings.pop(sequence, None)
    def pack(self, *args, **kwargs):
        self._mapped = True
    def grid(self, *args, **kwargs):
        self._mapped = True
    def place(self, *args, **kwargs):
        self._mapped = True
    def pack_configure(self, *args, **kwargs):
        pass
    def pack_forget(self, *args, **kwargs):
        self._mapped = False
    def grid_forget(self, *args, **kwargs):
        self._mapped = False
    def place_forget(self, *args, **kwargs):
        self._mapped = False
    def pack_propagate(self, *args, **kwargs):
        pass
    def grid_columnconfigure(self, *args, **kwargs):
        pass
    def columnconfigure(self, *args, **kwargs):
        pass
    def grid_rowconfigure(self, *args, **kwargs):
        pass
    def rowconfigure(self, *args, **kwargs):
        pass
    def configure(self, *args, **kwargs):
        self._config.update(kwargs)
    def cget(self, attr):
        return self._config.get(attr, "#000000")
    def delete(self, *args, **kwargs):
        pass
    def insert(self, *args, **kwargs):
        pass
    def get(self, *args, **kwargs):
        return ""
    def focus_set(self):
        pass
    def focus(self):
        pass
    def focus_force(self):
        pass
    def _on_close(self):
        pass
    def create_oval(self, *args, **kwargs):
        return 1
    def create_rectangle(self, *args, **kwargs):
        return 2
    def create_line(self, *args, **kwargs):
        return 3
    def itemconfig(self, *args, **kwargs):
        pass
    def coords(self, *args, **kwargs):
        pass
    def after(self, ms, func=None, *args):
        self._after_callbacks.append(func)
        return "job_1"
    def after_cancel(self, job):
        pass
    def execute_after_callbacks(self):
        callbacks = self._after_callbacks[:]
        self._after_callbacks.clear()
        for cb in callbacks:
            if cb:
                cb()
    def winfo_exists(self):
        return True
    def winfo_ismapped(self):
        return getattr(self, "_mapped", False)
    def winfo_reqwidth(self):
        return self._config.get("width", 100)
    def winfo_manager(self):
        return "pack"
    def winfo_children(self):
        return []
    def winfo_width(self):
        return 800
    def winfo_height(self):
        return 600
    def winfo_rootx(self):
        return 100
    def winfo_rooty(self):
        return 100
    def winfo_toplevel(self):
        return self
    def transient(self, *args, **kwargs):
        pass
    def grab_set(self, *args, **kwargs):
        pass
    def grab_release(self, *args, **kwargs):
        pass
    def title(self, *args, **kwargs):
        pass
    def geometry(self, *args, **kwargs):
        pass
    def resizable(self, *args, **kwargs):
        pass
    def destroy(self):
        self._exists = False
    def start(self, *args, **kwargs):
        pass
    def stop(self, *args, **kwargs):
        pass
    def set(self, val=None):
        pass

# Mock modules using DummyWidget classes
mock_tk = MagicMock()
mock_tk.Canvas = DummyWidget
mock_tk.Toplevel = DummyWidget

mock_ctk = MagicMock()
mock_ctk.CTkFrame = DummyWidget
mock_ctk.CTkButton = DummyWidget
mock_ctk.CTkLabel = DummyWidget
mock_ctk.CTkEntry = DummyWidget
mock_ctk.CTkScrollableFrame = DummyWidget
mock_ctk.CTkSlider = DummyWidget
mock_ctk.CTkSwitch = DummyWidget
mock_ctk.CTkRadioButton = DummyWidget
mock_ctk.CTkToplevel = DummyWidget
mock_ctk.CTkCheckBox = DummyWidget
mock_ctk.CTkProgressBar = DummyWidget

class DummyVar:
    def __init__(self, value=None): self._val = value
    def get(self): return self._val
    def set(self, val): self._val = val

mock_ctk.DoubleVar = DummyVar
mock_ctk.StringVar = DummyVar
mock_ctk.BooleanVar = DummyVar

_patcher = None
LolToggle = None
TabBar = None
CTkTooltip = None
Toast = None
ToastManager = None
ToastConfig = None

def _purge_ui_modules():
    """Drop every already-imported UI module so the next import sees the mocks.

    Without this the file passes alone and hangs the whole suite. Any earlier
    test that imports `ui.components.*` leaves those modules in `sys.modules`
    bound to the REAL customtkinter. Patching `sys.modules['customtkinter']`
    afterwards does nothing to them, so `TabBar(DummyWidget())` builds a real
    CTk widget on a MagicMock master. CustomTkinter then walks `master.master`
    looking for a Tk root -- and a MagicMock returns a fresh MagicMock for
    `.master` forever. Infinite loop, one new mock per turn, until the OOM
    killer takes the run down mid-file.
    """
    for mod in list(sys.modules):
        if mod == 'ui' or mod.startswith('ui.'):
            sys.modules.pop(mod, None)


def setUpModule():
    global _patcher, LolToggle, TabBar, CTkTooltip, Toast, ToastManager, ToastConfig
    _purge_ui_modules()
    _patcher = patch.dict(sys.modules, {
        'customtkinter': mock_ctk,
        'tkinter': mock_tk,
        'keyboard': MagicMock(),
    })
    _patcher.start()

    from ui.components.lol_toggle import LolToggle as LT
    from ui.components.tab_bar import TabBar as TB
    from ui.components.tooltip import CTkTooltip as CT
    from ui.components.toast import Toast as T, ToastManager as TM, ToastConfig as TC
    LolToggle = LT
    TabBar = TB
    CTkTooltip = CT
    Toast = T
    ToastManager = TM
    ToastConfig = TC

def tearDownModule():
    global _patcher
    if _patcher:
        _patcher.stop()
    # Leave nothing bound to the mock behind either -- the next file to import
    # these must get the real customtkinter back.
    _purge_ui_modules()
    for mod in list(sys.modules.keys()):
        if mod.startswith('utils.'):
            sys.modules.pop(mod, None)

class TestUIComponents(unittest.TestCase):

    def setUp(self):
        # setUpModule's patch.dict is still active; re-asserting it here only
        # guards against a test that swapped them out mid-file.
        sys.modules['customtkinter'] = mock_ctk
        sys.modules['tkinter'] = mock_tk
        self.mock_parent = DummyWidget()

    def test_lol_toggle_initialization(self):
        """Test LolToggle initialization and initial state setup."""
        mock_var = MagicMock()
        mock_var.get.return_value = True

        toggle = LolToggle(self.mock_parent, variable=mock_var)
        self.assertTrue(toggle._state)
        self.assertEqual(toggle._current_x, toggle.pos_on)

    def test_lol_toggle_toggle(self):
        """Test LolToggle state toggle and command execution."""
        mock_command = MagicMock()
        mock_var = MagicMock()
        mock_var.get.return_value = False

        toggle = LolToggle(self.mock_parent, variable=mock_var, command=mock_command)
        self.assertFalse(toggle._state)

        toggle.toggle()
        self.assertTrue(toggle._state)
        mock_var.set.assert_called_with(True)
        mock_command.assert_called_once()

    def test_lol_toggle_focus_events(self):
        """Test focus in and focus out events on LolToggle."""
        toggle = LolToggle(self.mock_parent)
        self.assertFalse(toggle._focused)

        toggle._on_focus_in()
        self.assertTrue(toggle._focused)

        toggle._on_focus_out()
        self.assertFalse(toggle._focused)

    def test_tab_bar_initialization(self):
        """Test TabBar initialization and default tab selection."""
        tabs = ["Home", "Settings", "About"]
        mock_command = MagicMock()

        tab_bar = TabBar(self.mock_parent, tabs=tabs, default_tab="Settings", command=mock_command)
        self.assertEqual(tab_bar.current_tab, "Settings")
        self.assertEqual(len(tab_bar.buttons), 3)

    def test_tab_bar_select_tab(self):
        """Test TabBar tab switching and callback invocation."""
        tabs = ["TabA", "TabB"]
        mock_command = MagicMock()

        tab_bar = TabBar(self.mock_parent, tabs=tabs, default_tab="TabA", command=mock_command)
        self.assertEqual(tab_bar.current_tab, "TabA")

        tab_bar.select_tab("TabB")
        self.assertEqual(tab_bar.current_tab, "TabB")
        mock_command.assert_called_with("TabB")

        # Selecting already selected tab should be no-op
        mock_command.reset_mock()
        tab_bar.select_tab("TabB")
        mock_command.assert_not_called()

    def test_ctk_tooltip(self):
        """Test CTkTooltip scheduling and configuration."""
        mock_widget = DummyWidget()
        mock_widget.after = MagicMock(return_value="job_1")
        mock_widget.after_cancel = MagicMock()

        tooltip = CTkTooltip(mock_widget, text="Test Tooltip", delay=200)

        self.assertEqual(tooltip.text, "Test Tooltip")
        self.assertEqual(tooltip.delay, 200)

        tooltip.configure(text="Updated Tooltip", delay=500)
        self.assertEqual(tooltip.text, "Updated Tooltip")
        self.assertEqual(tooltip.delay, 500)

        tooltip.schedule_show()
        mock_widget.after.assert_called_with(500, tooltip.show)

        tooltip.cancel_job()
        mock_widget.after_cancel.assert_called_once_with("job_1")

    def test_toast_manager_singleton(self):
        """Test ToastManager singleton instantiation."""
        ToastManager._instance = None
        mock_root = DummyWidget()

        tm = ToastManager.get_instance(mock_root)
        self.assertIsNotNone(tm)

        tm2 = ToastManager.get_instance()
        self.assertEqual(tm, tm2)

    def test_toast_config_resolution(self):
        """Test ToastConfig.resolve with direct config, kwargs, and positional args."""
        # Defaults
        cfg = ToastConfig.resolve()
        self.assertEqual(cfg.icon, "✨")
        self.assertEqual(cfg.duration, 3000)
        self.assertEqual(cfg.theme, "primary")
        self.assertFalse(cfg.confetti)

        # Direct instance
        custom_cfg = ToastConfig(icon="🔥", duration=1500, theme="error", confetti=True)
        resolved = ToastConfig.resolve(custom_cfg)
        self.assertEqual(resolved, custom_cfg)

        # Kwargs
        cfg_kw = ToastConfig.resolve(kwargs={"icon": "🎉", "theme": "success"})
        self.assertEqual(cfg_kw.icon, "🎉")
        self.assertEqual(cfg_kw.theme, "success")
        self.assertEqual(cfg_kw.duration, 3000)

        # Positional
        cfg_pos = ToastConfig.resolve(config="🚀", args=(5000, "error", True))
        self.assertEqual(cfg_pos.icon, "🚀")
        self.assertEqual(cfg_pos.duration, 5000)
        self.assertEqual(cfg_pos.theme, "error")
        self.assertTrue(cfg_pos.confetti)

        # Explicit None as first positional arg
        cfg_none_first = ToastConfig.resolve(config=None, args=(5000, "error"))
        self.assertEqual(cfg_none_first.icon, "✨")
        self.assertEqual(cfg_none_first.duration, 5000)
        self.assertEqual(cfg_none_first.theme, "error")

        # Instance with kwarg overrides
        cfg_override = ToastConfig.resolve(config=custom_cfg, kwargs={"theme": "success"})
        self.assertEqual(cfg_override.icon, "🔥")
        self.assertEqual(cfg_override.theme, "success")

    def test_toast_manager_show_and_eviction(self):
        """Test showing toasts and MAX_TOASTS eviction."""
        ToastManager._instance = None
        mock_root = DummyWidget()
        tm = ToastManager.get_instance(mock_root)

        for i in range(tm.MAX_TOASTS + 2):
            tm.show(f"Toast {i}")

        self.assertLessEqual(len(tm._toasts), tm.MAX_TOASTS)

    def test_toast_manager_show_flexible_signatures(self):
        """Test showing toasts with ToastConfig or keyword arguments."""
        ToastManager._instance = None
        mock_root = DummyWidget()
        tm = ToastManager.get_instance(mock_root)

        # With kwargs
        tm.show("Kwargs Toast", icon="✨", theme="success")
        self.assertEqual(len(tm._toasts), 1)

        # With ToastConfig
        cfg = ToastConfig(icon="🔥", theme="error")
        tm.show("Config Toast", config=cfg)
        self.assertEqual(len(tm._toasts), 2)

    def test_automation_editor_save(self):
        """Test AutomationEditor parameter saving for various automation keys."""
        sys.modules.pop("ui.components.automation_editor", None)
        from ui.components.automation_editor import AutomationEditor

        mock_master = DummyWidget()

        mock_config = MagicMock()
        mock_config.get.side_effect = lambda k, d=None: {
            "accept_delay": 2.0,
            "vip_invites_only": False,
            "vip_invite_list": "Faker",
            "honor_strategy": "friends",
            "runes_mode": "highest_winrate",
            "auto_add_position": "bottom",
            "auto_ban_1": "Yuumi",
            "auto_ban_respect_hovers": True
        }.get(k, d)

        keys_to_test = ["auto_accept", "auto_join", "auto_honor", "auto_runes", "auto_add_played", "auto_ban"]
        for key in keys_to_test:
            editor = AutomationEditor(mock_master, key, mock_config)

            # Mock variables so hasattr checks pass
            editor._show_icon_var = MagicMock()
            editor._delay_var = MagicMock()
            editor._honor_var = MagicMock()
            editor._vip_only_var = MagicMock()

            vip_list_mock = MagicMock()
            vip_list_mock.get.return_value = "Faker"
            editor._vip_list_var = vip_list_mock

            editor._runes_mode_var = MagicMock()
            editor._add_pos_var = MagicMock()

            ban_entry_mock = MagicMock()
            ban_entry_mock.get.return_value = "Yuumi"
            editor._ban_entries = [ban_entry_mock]

            editor._respect_hovers_var = MagicMock()

            editor._on_save()
            assert mock_config.set.call_count > 0

    def test_app_sidebar_navigation_tabs(self):
        """Test that top navigation bar includes Play, Accounts, Automations, Settings without Config."""
        expected_tabs = ["Play", "Accounts", "Automations", "Settings"]
        tab_bar = TabBar(self.mock_parent, tabs=expected_tabs, default_tab="Play")
        self.assertEqual(list(tab_bar.buttons.keys()), expected_tabs)
        self.assertNotIn("Config", tab_bar.buttons)

    def test_apply_click_animation(self):
        """Test the apply_click_animation utility function."""
        from unittest.mock import ANY
        from ui.components.hover import apply_click_animation

        # Setup mock widget
        mock_widget = MagicMock()
        mock_widget.cget.side_effect = lambda k: {
            "state": "normal",
            "fg_color": "#000000",
            "hover_color": "#111111"
        }.get(k)
        mock_widget.winfo_exists.return_value = True

        # MagicMock returns another MagicMock for any undefined attribute.
        # So `getattr(mock_widget, '_is_pulsing', False)` returns a truthy Mock object
        # instead of False unless explicitly set or deleted.
        if hasattr(mock_widget, "_is_pulsing"):
            del mock_widget._is_pulsing
        if hasattr(mock_widget, "_orig_pulse_fg"):
            del mock_widget._orig_pulse_fg
        if hasattr(mock_widget, "_orig_pulse_hover"):
            del mock_widget._orig_pulse_hover

        # Call function
        apply_click_animation(mock_widget, normal_color="#000000", pulse_color="#FF0000", button_num=1)

        # Verify bind was called
        mock_widget.bind.assert_called_with("<ButtonPress-1>", ANY, add="+")

        # Get the bound handler
        bind_args = mock_widget.bind.call_args
        on_click_handler = bind_args[0][1]

        # 1. Happy path: click it
        mock_widget.cget.side_effect = lambda k: {
            "state": "normal",
            "fg_color": "#000000",
            "hover_color": "#111111"
        }.get(k)
        on_click_handler(None)

        # Verify configure was called with pulse color
        mock_widget.configure.assert_called_with(fg_color="#FF0000", hover_color="#FF0000")

        # Verify it schedules a revert
        mock_widget.after.assert_called_once()
        after_args = mock_widget.after.call_args
        self.assertEqual(after_args[0][0], 150)
        revert_func = after_args[0][1]

        # Ensure _is_pulsing is set
        self.assertTrue(mock_widget._is_pulsing)

        # Execute revert and verify
        revert_func()
        mock_widget.configure.assert_called_with(fg_color="#000000", hover_color="#111111")
        self.assertFalse(mock_widget._is_pulsing)

        # 2. Disabled state
        mock_widget.reset_mock()
        mock_widget.cget.side_effect = lambda k: {
            "state": "disabled",
            "fg_color": "#000000",
            "hover_color": "#111111"
        }.get(k)
        on_click_handler(None)
        # Configure should not be called
        mock_widget.configure.assert_not_called()

        # 3. Re-entrancy check
        mock_widget.reset_mock()
        mock_widget.cget.side_effect = lambda k: {
            "state": "normal",
            "fg_color": "#000000",
            "hover_color": "#111111"
        }.get(k)
        mock_widget._is_pulsing = True
        on_click_handler(None)
        # Configure should not be called
        mock_widget.configure.assert_not_called()


    def test_apply_click_animation(self):
        """Test apply_click_animation binds properly, updates colors on click, and schedules reversion."""
        from ui.components.hover import apply_click_animation

        mock_widget = DummyWidget()
        mock_widget.configure(fg_color="#101010", hover_color="#202020", state="normal")

        # Test pulse_color argument
        apply_click_animation(mock_widget, normal_color="#101010", pulse_color="#FF0000")

        # Check if bound correctly
        self.assertIn("<ButtonPress-1>", mock_widget._bindings)
        handlers = mock_widget._bindings["<ButtonPress-1>"]
        self.assertGreater(len(handlers), 0)

        # Simulate click
        click_handler = handlers[0]
        click_handler(None)

        # Check colors changed to pulse_color
        self.assertEqual(mock_widget.cget("fg_color"), "#FF0000")
        self.assertEqual(mock_widget.cget("hover_color"), "#FF0000")
        self.assertTrue(mock_widget._is_pulsing)

        # Simulate double click prevention
        mock_widget.configure(fg_color="#00FF00", hover_color="#00FF00")
        click_handler(None)
        self.assertEqual(mock_widget.cget("fg_color"), "#00FF00") # Unchanged

        # Simulate reversion
        mock_widget.execute_after_callbacks()

        self.assertEqual(mock_widget.cget("fg_color"), "#101010")
        self.assertEqual(mock_widget.cget("hover_color"), "#202020")
        self.assertFalse(mock_widget._is_pulsing)

        # Test disabled state
        mock_widget.configure(state="disabled")
        click_handler(None)

    def test_feather_edge_component(self):
        """Test FeatherEdge gradient canvas initialization and color updates."""
        from ui.components.feather_edge import FeatherEdge, FeatherEdgeConfig
        fe = FeatherEdge(self.mock_parent, width=24, side="left")
        self.assertEqual(fe.feather_width, 24)
        self.assertEqual(fe.side, "left")

        # Test set_side
        fe.set_side("right")
        self.assertEqual(fe.side, "right")

        # Test color updates
        fe.update_colors(client_color="#000000", app_color="#101010", seam_color="#C8AA6E")
        self.assertEqual(fe.client_color, "#000000")
        self.assertEqual(fe.app_color, "#101010")
        self.assertEqual(fe.seam_color, "#C8AA6E")

        # Test initialization with FeatherEdgeConfig
        cfg = FeatherEdgeConfig(width=32, side="right", client_color="#111111", app_color="#222222", seam_color="#333333")
        fe_cfg = FeatherEdge(self.mock_parent, config=cfg)
        self.assertEqual(fe_cfg.feather_width, 32)
        self.assertEqual(fe_cfg.side, "right")
        self.assertEqual(fe_cfg.client_color, "#111111")
        self.assertEqual(fe_cfg.app_color, "#222222")
        self.assertEqual(fe_cfg.seam_color, "#333333")

    def test_sidebar_minimize_button_and_dock_styling(self):
        """Test minimize button and dock styling updates on SidebarWidget."""
        from ui.app_sidebar import SidebarWidget
        mock_master = DummyWidget()
        mock_master.minimize_window = MagicMock()
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda k, default=None: "ctrl+shift+a" if "hotkey" in k else default

        sidebar = SidebarWidget(mock_master, toggle_callback=MagicMock(), config=mock_config)
        self.assertTrue(hasattr(sidebar, "btn_minimize"))
        
        # Test minimize click triggers master.minimize_window
        sidebar._on_minimize_click()
        mock_master.minimize_window.assert_called_once()

        # Test dock styling update
        sidebar.update_dock_styling(docked=True)
        sidebar.update_dock_styling(docked=False)

    def test_sidebar_search_refusal_message(self):
        """Test _search_refusal_message extracts granular error reasons from client responses."""
        from ui.app_sidebar import SidebarWidget

        # None response
        self.assertEqual(
            SidebarWidget._search_refusal_message(None),
            "Matchmaking failed: no response from the League Client.",
        )

        # JSON with message
        mock_res_msg = MagicMock(status_code=400)
        mock_res_msg.json.return_value = {"message": "You cannot queue right now due to a penalty"}
        self.assertEqual(
            SidebarWidget._search_refusal_message(mock_res_msg),
            "Matchmaking failed: You cannot queue right now due to a penalty",
        )

        # JSON with nested errors list
        mock_res_err = MagicMock(status_code=400)
        mock_res_err.json.return_value = {"errors": [{"message": "Queue requires a party leader"}]}
        self.assertEqual(
            SidebarWidget._search_refusal_message(mock_res_err),
            "Matchmaking failed: Queue requires a party leader",
        )

        # HTTP 400 without specific message body
        mock_res_400 = MagicMock(status_code=400)
        mock_res_400.json.side_effect = ValueError("Invalid JSON")
        self.assertEqual(
            SidebarWidget._search_refusal_message(mock_res_400, mode="Ranked Solo/Duo"),
            "Matchmaking failed: queue unavailable or requirements not met (Ranked Solo/Duo).",
        )

        # HTTP 404
        mock_res_404 = MagicMock(status_code=404)
        mock_res_404.json.side_effect = ValueError("Invalid JSON")
        self.assertEqual(
            SidebarWidget._search_refusal_message(mock_res_404),
            "Matchmaking failed: lobby not found.",
        )

        # HTTP 500
        mock_res_500 = MagicMock(status_code=500)
        mock_res_500.json.side_effect = ValueError("Invalid JSON")
        self.assertEqual(
            SidebarWidget._search_refusal_message(mock_res_500),
            "Matchmaking failed (HTTP 500).",
        )

    def test_loot_tool_visuals_and_telemetry(self):
        """Test LootTool visual elements, telemetry chips, category mapping and busy states."""
        from ui.components.game_tools.loot_tool import LootTool, _get_loot_visuals
        mock_lcu = MagicMock()
        mock_lcu.is_connected = True

        # Test category visuals mapping
        self.assertEqual(_get_loot_visuals("CHEST_1", "Hextech Chest", "CHEST", "CHEST")["icon"], "📦")
        self.assertEqual(_get_loot_visuals("CHEST_masterwork", "Masterwork Chest", "CHEST", "CHEST")["icon"], "👑")
        self.assertEqual(_get_loot_visuals("CHEST_capsule", "Champion Capsule", "CHEST", "CHEST")["icon"], "💎")
        self.assertEqual(_get_loot_visuals("ORB_event", "Arcane Orb", "ORB", "ORB")["icon"], "🔮")
        self.assertEqual(_get_loot_visuals("EGG_tft", "TFT Egg", "EGG", "TFT")["icon"], "🥚")

        tool = LootTool(self.mock_parent, lcu=mock_lcu)
        self.assertIsNotNone(tool.stats_frame)
        self.assertIsNotNone(tool.progress_bar)

        rows = [
            {"loot_id": "CHEST_1", "name": "Hextech Chest", "count": 2, "type": "CHEST", "category": "CHEST", "can_open": True, "will_open": 2, "needs_key": False},
            {"loot_id": "CHEST_2", "name": "Masterwork Chest", "count": 1, "type": "CHEST", "category": "CHEST", "can_open": False, "will_open": 0, "needs_key": True},
        ]
        tool._render_rows(rows, keys=3, frags=5)
        self.assertEqual(tool.lbl_stat_openable_num.cget("text"), "2")
        self.assertEqual(tool.lbl_stat_keys_num.cget("text"), "3")
        self.assertEqual(tool.lbl_stat_frags_num.cget("text"), "5")

        # Test stat chips have width=60 to prevent width overflow
        self.assertEqual(tool.chip_openable.cget("width"), 60)
        self.assertEqual(tool.chip_keys.cget("width"), 60)
        self.assertEqual(tool.chip_frags.cget("width"), 60)

        # Test options labels and separation
        self.assertEqual(tool.chk_claim.cget("text"), "Claim rewards first")
        self.assertEqual(tool.chk_keys.cget("text"), "Craft keys first")
        self.assertIsNotNone(tool.summary_frame)
        self.assertIsNotNone(tool.summary_lbl)

        # Test responsive action layout: Stop button hidden when idle, shown when busy
        self.assertFalse(tool.btn_stop.winfo_ismapped())
        tool._set_busy(True)
        self.assertEqual(tool.btn_open.cget("state"), "disabled")
        self.assertTrue(tool.btn_stop.winfo_ismapped())
        tool._set_busy(False)
        self.assertEqual(tool.btn_open.cget("state"), "normal")
        self.assertFalse(tool.btn_stop.winfo_ismapped())

        # Test responsive inventory height
        tool._render_rows([])
        self.assertEqual(tool.list_frame.cget("height"), 125)

        single_row = [{"loot_id": "CHEST_1", "name": "Box", "count": 1, "type": "CHEST", "category": "CHEST", "can_open": True, "will_open": 1, "needs_key": False}]
        tool._render_rows(single_row)
        self.assertEqual(tool.list_frame.cget("height"), 60)  # max(60, min(170, 1 * 52 + 6)) = 60

        ten_rows = [{"loot_id": f"C_{i}", "name": f"Box {i}", "count": 1, "type": "CHEST", "category": "CHEST", "can_open": True, "will_open": 1, "needs_key": False} for i in range(10)]
        tool._render_rows(ten_rows)
        self.assertEqual(tool.list_frame.cget("height"), 170)  # clamped at max 170

    def test_settings_toggle_row_balanced_wrap(self):
        """A too-long toggle label splits into even lines, never a one-word orphan."""
        from ui.components.settings_row import SettingsToggleRow
        self.assertEqual(SettingsToggleRow.balanced_wrap(120, 200), 0)  # fits: no wrap
        self.assertEqual(SettingsToggleRow.balanced_wrap(220, 170), 122)  # 2 lines of ~110
        self.assertEqual(SettingsToggleRow.balanced_wrap(500, 170), 170)  # capped at the space
        self.assertEqual(SettingsToggleRow.balanced_wrap(220, 0), 0)

    def test_settings_action_row_responsive(self):
        """Test SettingsActionRow text wrapping, reserved button width, loading and status clearing."""
        from ui.components.settings_row import SettingsActionRow
        row = SettingsActionRow(
            self.mock_parent,
            label_text="Kill Unnecessary Windows Processes",
            description="Safely purge updaters, telemetry, & idle hogs",
            button_text="Kill Processes",
            button_width=105,
            command=MagicMock(),
        )
        self.assertIsNotNone(row.button)
        self.assertIsNotNone(row.text_label)
        self.assertIsNotNone(row.desc_label)
        self.assertIsNotNone(row.status_label)

        # Test configure event dynamic wraplength update
        row.winfo_width = MagicMock(return_value=280)
        row.button.winfo_reqwidth = MagicMock(return_value=105)
        row._on_configure()
        self.assertEqual(row.text_label.cget("wraplength"), 161)  # 280 - 105 - 14
        self.assertEqual(row.desc_label.cget("wraplength"), 161)
        self.assertEqual(row.status_label.cget("wraplength"), 272)

        # Test set_loading preserves button visibility without disabling
        row.set_loading(True, "Working...")
        self.assertEqual(row.button.cget("text"), "Working...")
        self.assertNotEqual(row.button.cget("state"), "disabled")
        row.set_loading(False)
        self.assertEqual(row.button.cget("text"), "Kill Processes")

        # Test set_status and clear_status
        row.set_status("✓ Optimized successfully", is_error=False)
        self.assertEqual(row.status_label.cget("text"), "✓ Optimized successfully")
        self.assertTrue(row.status_label.winfo_ismapped())
        row.clear_status()
        self.assertEqual(row.status_label.cget("text"), "")
        self.assertFalse(row.status_label.winfo_ismapped())


if __name__ == '__main__':
    unittest.main()
