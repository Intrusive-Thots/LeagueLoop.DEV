"""
The Accounts screen must switch into the account the user clicked.

Display order (most recent first) and storage order are deliberately
different, so every row has to carry the stored index rather than its
position on screen.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class FakeAccountsService:
    """Storage order: Main, Smurf, Fresh. Display order: Smurf, Main, Fresh."""

    STORED = [
        {"label": "Main", "username": "main", "last_used": "2026-01-01T00:00:00"},
        {"label": "Smurf", "username": "smurf", "last_used": "2026-06-01T00:00:00"},
        {"label": "Fresh", "username": "fresh", "last_used": None},
    ]
    DISPLAY_ORDER = [1, 0, 2]

    def __init__(self):
        self.logins = []
        self.defaults = []

    def get_accounts(self):
        return [dict(a) for a in self.STORED]

    def get_accounts_display(self):
        return [(i, dict(self.STORED[i])) for i in self.DISPLAY_ORDER]

    def get_active_index(self):
        return 1

    def get_default_account_index(self):
        return 0

    def login_account(self, index):
        self.logins.append(index)

    def set_default_account(self, index):
        self.defaults.append(index)


class FakeContainer:
    def __init__(self, service):
        self.account_manager = service


class QtAccountsTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from ui.qt.widgets.accounts_tab import QtAccountsTab
        self.service = FakeAccountsService()
        self.tab = QtAccountsTab(container=FakeContainer(self.service))

    def _switch_buttons(self):
        return [b for b in self.tab._buttons if b.text() == "Switch"]

    def test_rows_render_in_display_order(self):
        from PySide6.QtWidgets import QLabel
        names = []
        for row in self.tab._rows:
            label = row.findChild(QLabel)
            if label is not None:
                names.append(label.text())
        self.assertEqual(names, ["Smurf", "Main", "Fresh"])

    def test_clicking_a_row_switches_to_the_account_shown_on_it(self):
        buttons = self._switch_buttons()
        self.assertEqual(len(buttons), 3)

        # Second row on screen is "Main", which is stored at index 0.
        buttons[1].click()
        self.assertEqual(self.service.logins, [0])

        # A switch in flight locks the list; nothing else can be started.
        buttons[2].click()
        self.assertEqual(self.service.logins, [0])

        # Once it finishes, the third row ("Fresh") switches to index 2.
        self.tab._on_switch_finished(None)
        self._switch_buttons()[2].click()
        self.assertEqual(self.service.logins, [0, 2])

    def test_active_row_cannot_switch_to_itself(self):
        # "Smurf" (stored index 1) is active and is rendered first.
        self.assertFalse(self._switch_buttons()[0].isEnabled())

    def test_set_default_uses_the_stored_index(self):
        defaults = [b for b in self.tab._buttons if b.text() == "Set default"]
        defaults[2].click()  # "Fresh" on screen, stored index 2
        self.assertEqual(self.service.defaults, [2])

    def test_busy_state_does_not_re_enable_deliberately_disabled_buttons(self):
        self.tab._set_busy(True)
        self.assertTrue(all(not b.isEnabled() for b in self.tab._buttons))

        self.tab._set_busy(False)
        # Row 0 is the active account ("Smurf"); it must still refuse a switch.
        self.assertFalse(self._switch_buttons()[0].isEnabled())
        self.assertTrue(self._switch_buttons()[1].isEnabled())

    def test_falls_back_to_plain_getter_when_display_api_is_absent(self):
        """An older account service without the display API must still work."""
        from ui.qt.widgets.accounts_tab import QtAccountsTab

        class LegacyService(FakeAccountsService):
            get_accounts_display = None  # present but not callable

        tab = QtAccountsTab(container=FakeContainer(LegacyService()))
        self.assertEqual([i for i, _ in tab._accounts()], [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
