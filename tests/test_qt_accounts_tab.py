"""
The Accounts screen must switch into the account the user clicked.

Rows render in **stored** order — the order the user arranges with the
reorder arrows. The screen previously rendered `get_accounts_display()`,
which sorts by `last_used`; since the arrows change stored order, pressing
one swapped two rows in the file and the screen re-sorted straight back, so
the arrows appeared to do nothing.

Every row still carries the stored index rather than its screen position,
which is what `login_account`, `set_default_account` and the switcher expect.
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
    #: Rows render in stored order now, so this mirrors STORED.
    DISPLAY_ORDER = [0, 1, 2]

    def __init__(self):
        self.logins = []
        self.defaults = []
        self.added = []
        self.edited = []
        self.deleted = []
        self.STORED = [dict(a) for a in type(self).STORED]

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

    def add_account(self, label, username, password, tagline="", region="NA1"):
        self.added.append((label, username, password, tagline, region))
        self.STORED.append({"label": label, "username": username,
                            "last_used": None})
        self.DISPLAY_ORDER = list(range(len(self.STORED)))
        return len(self.STORED) - 1

    def edit_account(self, index, **kw):
        self.edited.append((index, kw))

    def delete_account(self, index):
        self.deleted.append(index)
        self.STORED.pop(index)
        self.DISPLAY_ORDER = list(range(len(self.STORED)))


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

    def test_rows_render_in_stored_order(self):
        """The order the user arranged, not one the app re-derives."""
        from PySide6.QtWidgets import QLabel
        names = []
        for row in self.tab._rows:
            label = row.findChild(QLabel)
            if label is not None:
                names.append(label.text())
        self.assertEqual(names, ["Main", "Smurf", "Fresh"])

    def test_clicking_a_row_switches_to_the_account_shown_on_it(self):
        buttons = self._switch_buttons()
        self.assertEqual(len(buttons), 3)

        # First row is "Main", stored index 0. (Row 1 is "Smurf", the active
        # account, whose Switch is correctly disabled.)
        buttons[0].click()
        self.assertEqual(self.service.logins, [0])

        # A switch in flight locks the list; nothing else can be started.
        buttons[2].click()
        self.assertEqual(self.service.logins, [0])

        # Once it finishes, the third row ("Fresh") switches to index 2.
        self.tab._apply_switch_finished(None)
        self._switch_buttons()[2].click()
        self.assertEqual(self.service.logins, [0, 2])

    def test_missing_credentials_are_flagged_before_a_switch_is_tried(self):
        from ui.qt.widgets.accounts_tab import QtAccountsTab

        class Broken(FakeAccountsService):
            def has_valid_credentials(self, index):
                return index != 2  # "Fresh" has no usable password

        tab = QtAccountsTab(container=FakeContainer(Broken()))
        texts = []
        for row in tab._rows:
            from ui.qt.components.badge import LLBadge
            texts.append([b.text() for b in row.findChildren(LLBadge)])
        # Stored order is Main, Smurf, Fresh; index 2 is "Fresh".
        self.assertNotIn("No password", texts[0])
        self.assertNotIn("No password", texts[1])
        self.assertIn("No password", texts[2])

    def test_unknown_credential_state_is_not_shown_as_a_problem(self):
        from ui.qt.components.badge import LLBadge
        for row in self.tab._rows:
            self.assertNotIn(
                "No password", [b.text() for b in row.findChildren(LLBadge)]
            )

    def test_region_is_not_repeated_when_the_riot_id_already_carries_it(self):
        from PySide6.QtWidgets import QLabel

        class Dupe(FakeAccountsService):
            STORED = [{"label": "EU", "username": "eu", "tagline": "Name#EUW1",
                       "region": "EUW1", "last_used": None}]
            DISPLAY_ORDER = [0]

            def get_active_index(self): return -1
            def get_default_account_index(self): return -1

        from ui.qt.widgets.accounts_tab import QtAccountsTab
        tab = QtAccountsTab(container=FakeContainer(Dupe()))
        detail = " ".join(l.text() for l in tab._rows[0].findChildren(QLabel))
        self.assertIn("Name#EUW1", detail)
        self.assertNotIn("Name#EUW1 - EUW1", detail)

    def test_active_row_cannot_switch_to_itself(self):
        # "Smurf" is stored index 1 and is active; it renders second.
        self.assertFalse(self._switch_buttons()[1].isEnabled())

    def test_set_default_uses_the_stored_index(self):
        defaults = [b for b in self.tab._buttons if b.text() == "Set default"]
        defaults[2].click()  # "Fresh" on screen, stored index 2
        self.assertEqual(self.service.defaults, [2])

    def test_busy_state_does_not_re_enable_deliberately_disabled_buttons(self):
        self.tab._set_busy(True)
        self.assertTrue(all(not b.isEnabled() for b in self.tab._buttons))

        self.tab._set_busy(False)
        # Row 1 is the active account ("Smurf"); it must still refuse a switch.
        self.assertFalse(self._switch_buttons()[1].isEnabled())
        self.assertTrue(self._switch_buttons()[0].isEnabled())

    def test_falls_back_to_plain_getter_when_display_api_is_absent(self):
        """An older account service without the display API must still work."""
        from ui.qt.widgets.accounts_tab import QtAccountsTab

        class LegacyService(FakeAccountsService):
            get_accounts_display = None  # present but not callable

        tab = QtAccountsTab(container=FakeContainer(LegacyService()))
        self.assertEqual([i for i, _ in tab._accounts()], [0, 1, 2])


if __name__ == "__main__":
    unittest.main()


class QtAccountsCrudTests(unittest.TestCase):
    """Add / edit / remove are wired to the *stored* index, and confirmed."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from ui.qt.widgets.accounts_tab import QtAccountsTab
        self.service = FakeAccountsService()
        self.tab = QtAccountsTab(container=FakeContainer(self.service))

    def _buttons(self, text):
        return [b for b in self.tab._buttons if b.text() == text]

    # -- helpers to run a modal without showing it ------------------------
    def _auto_accept(self, monkey_target, fill=None):
        """Replace exec() so the dialog resolves immediately."""
        import ui.qt.widgets.accounts_tab as mod
        original = getattr(mod, monkey_target)

        class Auto(original):
            def exec(self_inner):
                if fill:
                    fill(self_inner)
                return original.Accepted

        setattr(mod, monkey_target, Auto)
        self.addCleanup(setattr, mod, monkey_target, original)

    def _auto_reject(self, monkey_target):
        import ui.qt.widgets.accounts_tab as mod
        original = getattr(mod, monkey_target)

        class Auto(original):
            def exec(self_inner):
                return original.Rejected

        setattr(mod, monkey_target, Auto)
        self.addCleanup(setattr, mod, monkey_target, original)

    # -- add ---------------------------------------------------------------
    def test_add_passes_the_entered_values_through(self):
        def fill(dialog):
            dialog.field_label.set_text("Alt")
            dialog.field_username.set_text("altuser")
            dialog.field_password.set_text("pw")
            dialog.field_region.set_text("euw1")

        self._auto_accept("AccountEditorModal", fill)
        self.tab.btn_add.click()

        self.assertEqual(len(self.service.added), 1)
        label, username, password, tagline, region = self.service.added[0]
        self.assertEqual((label, username, password, region),
                         ("Alt", "altuser", "pw", "EUW1"))

    def test_cancelling_add_changes_nothing(self):
        self._auto_reject("AccountEditorModal")
        self.tab.btn_add.click()
        self.assertEqual(self.service.added, [])

    def test_first_account_becomes_the_default(self):
        from ui.qt.widgets.accounts_tab import QtAccountsTab
        service = FakeAccountsService()
        service.STORED = []
        service.DISPLAY_ORDER = []
        tab = QtAccountsTab(container=FakeContainer(service))

        def fill(dialog):
            dialog.field_username.set_text("first")
            dialog.field_password.set_text("pw")

        self._auto_accept("AccountEditorModal", fill)
        # The empty state's call to action is the only button present.
        tab._buttons[0].click()

        self.assertEqual(service.added and service.added[0][1], "first")
        self.assertEqual(service.defaults, [0])

    # -- edit --------------------------------------------------------------
    def test_edit_targets_the_account_shown_on_the_row(self):
        self._auto_accept(
            "AccountEditorModal",
            lambda d: d.field_label.set_text("Renamed"),
        )
        # Second row on screen is "Smurf", stored at index 1.
        self._buttons("Edit")[1].click()

        self.assertEqual(len(self.service.edited), 1)
        index, kwargs = self.service.edited[0]
        self.assertEqual(index, 1)
        self.assertEqual(kwargs["label"], "Renamed")

    def test_editing_without_touching_the_password_sends_none(self):
        self._auto_accept("AccountEditorModal")
        self._buttons("Edit")[0].click()
        _index, kwargs = self.service.edited[0]
        self.assertIsNone(kwargs["password"])

    # -- remove ------------------------------------------------------------
    def test_remove_asks_first(self):
        self._auto_reject("LLConfirmModal")
        self._buttons("Remove")[0].click()
        self.assertEqual(self.service.deleted, [])

    def test_remove_targets_the_account_shown_on_the_row(self):
        self._auto_accept("LLConfirmModal")
        # Third row is "Fresh", stored at index 2.
        self._buttons("Remove")[2].click()
        self.assertEqual(self.service.deleted, [2])

    def test_removing_the_default_promotes_another(self):
        self._auto_accept("LLConfirmModal")
        # "Main" is stored index 0 and is the default; it is the first row.
        self._buttons("Remove")[0].click()
        self.assertEqual(self.service.deleted, [0])
        self.assertTrue(self.service.defaults,
                        "no account was promoted to default")


class UnrecognisedAccountTests(unittest.TestCase):
    """Being signed in as an unsaved account is offered, never auto-created."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self, identity):
        from ui.qt.widgets.accounts_tab import QtAccountsTab

        class Service(FakeAccountsService):
            def get_unrecognised_identity(self_inner):
                return identity

        self.service = Service()
        return QtAccountsTab(container=FakeContainer(self.service))

    def test_card_is_hidden_when_everything_is_recognised(self):
        tab = self._tab(None)
        self.assertFalse(tab.unknown_card.isVisible())

    def test_card_names_the_account_the_client_is_on(self):
        tab = self._tab({"username": "stranger", "tagline": "stranger#na1",
                         "display_name": "stranger#na1"})
        self.assertTrue(tab.unknown_card.isVisibleTo(tab))
        self.assertIn("stranger#na1", tab.unknown_label.text())

    def test_saving_prefills_the_editor_and_asks_for_a_password(self):
        import ui.qt.widgets.accounts_tab as mod

        tab = self._tab({"username": "stranger", "tagline": "stranger#na1",
                         "display_name": "stranger#na1"})
        seen = {}
        original = mod.AccountEditorModal

        class Auto(original):
            def exec(self_inner):
                seen["username"] = self_inner.field_username.text()
                seen["tagline"] = self_inner.field_tagline.text()
                self_inner.field_password.set_text("pw")
                return original.Accepted

        mod.AccountEditorModal = Auto
        self.addCleanup(setattr, mod, "AccountEditorModal", original)

        tab.btn_save_unknown.click()

        self.assertEqual(seen["username"], "stranger")
        self.assertEqual(seen["tagline"], "stranger#na1")
        self.assertEqual(len(self.service.added), 1)
        self.assertEqual(self.service.added[0][2], "pw")

    def test_declining_saves_nothing(self):
        import ui.qt.widgets.accounts_tab as mod

        tab = self._tab({"username": "stranger", "tagline": "",
                         "display_name": "stranger"})
        original = mod.AccountEditorModal

        class Auto(original):
            def exec(self_inner):
                return original.Rejected

        mod.AccountEditorModal = Auto
        self.addCleanup(setattr, mod, "AccountEditorModal", original)

        tab.btn_save_unknown.click()
        self.assertEqual(self.service.added, [])

    def test_a_service_without_the_api_is_tolerated(self):
        from ui.qt.widgets.accounts_tab import QtAccountsTab
        tab = QtAccountsTab(container=FakeContainer(FakeAccountsService()))
        self.assertFalse(tab.unknown_card.isVisible())


class DetectionWiringTests(unittest.TestCase):
    """The screen asks who is signed in, without blocking the GUI thread."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_detection_runs_and_refreshes_when_it_lands(self):
        from PySide6.QtCore import QThreadPool
        from ui.qt.widgets.accounts_tab import QtAccountsTab

        calls = []

        class Service(FakeAccountsService):
            def detect_active_account(self_inner):
                calls.append("detect")
                return 0

        tab = QtAccountsTab(container=FakeContainer(Service()))
        QThreadPool.globalInstance().waitForDone(2000)
        self.app.processEvents()

        self.assertIn("detect", calls)
        self.assertTrue(tab._rows, "the list did not render after detection")

    def test_a_service_that_cannot_detect_is_not_an_error(self):
        from PySide6.QtCore import QThreadPool
        from ui.qt.widgets.accounts_tab import QtAccountsTab

        class Angry(FakeAccountsService):
            def detect_active_account(self_inner):
                raise RuntimeError("client exploded")

        tab = QtAccountsTab(container=FakeContainer(Angry()))
        QThreadPool.globalInstance().waitForDone(2000)
        self.app.processEvents()
        self.assertTrue(tab._rows)

    def test_detection_is_skipped_while_a_switch_is_in_flight(self):
        from ui.qt.widgets.accounts_tab import QtAccountsTab

        calls = []

        class Service(FakeAccountsService):
            def detect_active_account(self_inner):
                calls.append(1)
                return 0

        tab = QtAccountsTab(container=FakeContainer(Service()))
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().waitForDone(2000)
        before = len(calls)

        from PySide6.QtGui import QShowEvent
        tab._set_busy(True)
        tab.showEvent(QShowEvent())
        QThreadPool.globalInstance().waitForDone(500)
        self.assertEqual(len(calls), before,
                         "detection raced a switch that was already running")


class ThreadAffinityTests(unittest.TestCase):
    """
    Switch events arrive on the switcher's worker thread. `refresh()` builds
    and destroys QWidgets, which is only legal on the GUI thread - doing it
    inline is why the stored-account list came back empty after a failed
    switch.
    """

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from ui.qt.widgets.accounts_tab import QtAccountsTab
        self.service = FakeAccountsService()
        self.tab = QtAccountsTab(container=FakeContainer(self.service))

    def test_bus_callbacks_do_not_touch_widgets_directly(self):
        import threading

        rendered_before = len(self.tab._rows)
        errors = []

        def worker():
            try:
                self.tab._on_switch_finished(None)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(2)

        self.assertEqual(errors, [])
        # Nothing has been rebuilt yet - the work is queued, not done inline.
        self.assertEqual(len(self.tab._rows), rendered_before)

        self.app.processEvents()
        self.assertTrue(self.tab._rows, "the queued refresh never ran")

    def test_the_list_survives_a_failed_switch(self):
        class Failed:
            ok = False
            message = "Could not sign out the current account."
            detail = ""
            outcome = type("O", (), {"value": "sign_out_failed"})()

        self.tab._on_switch_finished(Failed())
        self.app.processEvents()

        self.assertEqual(len(self.tab._rows), 3,
                         "the stored accounts vanished after a failed switch")
        self.assertIn("sign out", self.tab.active_status.text().lower())


class ReorderTests(unittest.TestCase):
    """
    The reorder arrows must visibly move a row.

    They call `move_account()`, which changes stored order. The screen used to
    render `get_accounts_display()`, which sorts by `last_used` — so the swap
    happened in the file and the display re-sorted straight back. The arrows
    looked broken.
    """

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        from ui.qt.widgets.accounts_tab import QtAccountsTab

        class Service(FakeAccountsService):
            def get_active_index(self_inner): return -1
            def get_default_account_index(self_inner): return -1

            def move_account(self_inner, index, direction):
                target = index + direction
                if 0 <= target < len(self_inner.STORED):
                    self_inner.STORED[index], self_inner.STORED[target] = (
                        self_inner.STORED[target], self_inner.STORED[index]
                    )

        self.service = Service()
        return QtAccountsTab(container=FakeContainer(self.service))

    def _names(self, tab):
        from PySide6.QtWidgets import QLabel
        return [row.findChild(QLabel).text() for row in tab._rows]

    def test_moving_a_row_down_changes_what_is_on_screen(self):
        tab = self._tab()
        self.assertEqual(self._names(tab), ["Main", "Smurf", "Fresh"])

        down = [b for b in tab._buttons if b.text() == "▼"]
        self.assertTrue(down, "no reorder controls rendered")
        down[0].click()

        self.assertEqual(self._names(tab), ["Smurf", "Main", "Fresh"])

    def test_recency_is_shown_rather_than_used_as_ordering(self):
        tab = self._tab()
        detail = " ".join(
            l.text() for l in tab._rows[2].findChildren(type(tab._rows[2]).__mro__[0])
        ) if False else ""
        from PySide6.QtWidgets import QLabel
        detail = " ".join(l.text() for l in tab._rows[2].findChildren(QLabel))
        self.assertIn("never used", detail)


class LastUsedLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _label(self, value):
        from ui.qt.widgets.accounts_tab import QtAccountsTab
        return QtAccountsTab._last_used_label(value)

    def test_never(self):
        self.assertEqual(self._label(None), "never used")

    def test_relative_days(self):
        from datetime import datetime, timedelta
        self.assertEqual(
            self._label((datetime.now() - timedelta(days=1)).isoformat()),
            "used yesterday",
        )
        self.assertIn(
            "days ago",
            self._label((datetime.now() - timedelta(days=5)).isoformat()),
        )

    def test_months(self):
        from datetime import datetime, timedelta
        self.assertIn(
            "month",
            self._label((datetime.now() - timedelta(days=70)).isoformat()),
        )

    def test_garbage_is_dropped_not_shown(self):
        self.assertEqual(self._label("not-a-date"), "")
