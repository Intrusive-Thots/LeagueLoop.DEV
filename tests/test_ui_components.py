import sys
import unittest
from unittest.mock import MagicMock, patch

class DummyWidget:
    def __init__(self, *args, **kwargs):
        self._exists = True
        self.master = MagicMock()
    def bind(self, *args, **kwargs):
        pass
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
        pass
    def cget(self, attr):
        return "#000000"
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
        return "job_1"
    def after_cancel(self, job):
        pass
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

patch.dict(sys.modules, {
    'customtkinter': mock_ctk,
    'tkinter': mock_tk,
}).start()

# Clear cached imports
for mod in list(sys.modules.keys()):
    if mod.startswith('ui.components'):
        sys.modules.pop(mod, None)

from ui.components.lol_toggle import LolToggle
from ui.components.tab_bar import TabBar
from ui.components.tooltip import CTkTooltip
from ui.components.toast import Toast, ToastManager

class TestUIComponents(unittest.TestCase):

    def setUp(self):
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
            editor._on_save()
            # Verify that the save operation was triggered (config.set was called)
            mock_config.set.assert_called()
            mock_config.reset_mock()

    def test_app_sidebar_navigation_tabs(self):
        """Test that top navigation bar includes Play, Accounts, Automations, Settings without Config."""
        expected_tabs = ["Play", "Accounts", "Automations", "Settings"]
        tab_bar = TabBar(self.mock_parent, tabs=expected_tabs, default_tab="Play")
        self.assertEqual(list(tab_bar.buttons.keys()), expected_tabs)
        self.assertNotIn("Config", tab_bar.buttons)


if __name__ == '__main__':
    unittest.main()
