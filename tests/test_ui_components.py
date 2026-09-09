import sys
import unittest
from unittest.mock import MagicMock, patch

class DummyWidget:
    def __init__(self, *args, **kwargs):
        self._exists = True
        self.master = MagicMock()
        self.tk = MagicMock()
        self._w = ".dummy"
        self._last_child_ids = {}
        self.children = {}
        self._config = {"state": "normal", "fg_color": "#000000", "hover_color": "#333333"}
        self._bindings = {}
        self._after_callbacks = []
    def bind(self, sequence, func=None, add=None):
        if add == "+":
            if sequence not in self._bindings:
                self._bindings[sequence] = []
            self._bindings[sequence].append(func)
        else:
            self._bindings[sequence] = [func]
    def pack(self, *args, **kwargs):
        pass
    def grid(self, *args, **kwargs):
        pass
    def place(self, *args, **kwargs):
        pass
    def pack_configure(self, *args, **kwargs):
        pass
    def pack_forget(self, *args, **kwargs):
        pass
    def grid_forget(self, *args, **kwargs):
        pass
    def place_forget(self, *args, **kwargs):
        pass
    def pack_propagate(self, *args, **kwargs):
        pass
    def grid_columnconfigure(self, *args, **kwargs):
        pass
    def grid_rowconfigure(self, *args, **kwargs):
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
    global _patcher, LolToggle, TabBar, CTkTooltip, Toast, ToastManager
    _purge_ui_modules()
    _patcher = patch.dict(sys.modules, {
        'customtkinter': mock_ctk,
        'tkinter': mock_tk,
    })
    _patcher.start()

    from ui.components.lol_toggle import LolToggle as LT
    from ui.components.tab_bar import TabBar as TB
    from ui.components.tooltip import CTkTooltip as CT
    from ui.components.toast import Toast as T, ToastManager as TM
    LolToggle = LT
    TabBar = TB
    CTkTooltip = CT
    Toast = T
    ToastManager = TM

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

    def test_toast_manager_show_and_eviction(self):
        """Test showing toasts and MAX_TOASTS eviction."""
        ToastManager._instance = None
        mock_root = DummyWidget()
        tm = ToastManager.get_instance(mock_root)

        for i in range(tm.MAX_TOASTS + 2):
            tm.show(f"Toast {i}")

        self.assertLessEqual(len(tm._toasts), tm.MAX_TOASTS)

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

if __name__ == '__main__':
    unittest.main()
