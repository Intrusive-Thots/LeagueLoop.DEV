"""
The account editor is the one screen that handles a password, so its
behaviour is pinned rather than left to inspection.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class AccountEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _new(self, **kw):
        from ui.qt.widgets.account_editor import AccountEditorModal
        return AccountEditorModal(**kw)

    # ------------------------------------------------------------ adding
    def test_new_account_requires_username_and_password(self):
        dialog = self._new()
        self.assertFalse(dialog.validate())
        self.assertTrue(dialog.field_username.has_error())
        self.assertTrue(dialog.field_password.has_error())

    def test_all_problems_are_reported_at_once(self):
        """Not one per submit — that turns one form into three round trips."""
        dialog = self._new()
        dialog.field_tagline.set_text("no-hash")
        dialog.field_region.set_text("")
        self.assertFalse(dialog.validate())
        self.assertTrue(dialog.field_username.has_error())
        self.assertTrue(dialog.field_password.has_error())
        self.assertTrue(dialog.field_tagline.has_error())
        self.assertTrue(dialog.field_region.has_error())

    def test_riot_id_pasted_into_the_username_field_is_caught(self):
        dialog = self._new()
        dialog.field_username.set_text("DPM#Null")
        dialog.field_password.set_text("pw")
        self.assertFalse(dialog.validate())
        self.assertIn("Riot ID", dialog.field_username.message.text())

    def test_duplicate_username_is_rejected(self):
        dialog = self._new(existing_usernames=["themalcolm3"])
        dialog.field_username.set_text("TheMalcolm3")  # case-insensitive
        dialog.field_password.set_text("pw")
        self.assertFalse(dialog.validate())
        self.assertIn("already stored", dialog.field_username.message.text())

    def test_valid_new_account_passes_and_reports_values(self):
        dialog = self._new()
        dialog.field_username.set_text("  themalcolm3 ")
        dialog.field_password.set_text("hunter2")
        dialog.field_tagline.set_text("DPM#Null")
        dialog.field_region.set_text("na1")

        self.assertTrue(dialog.validate())
        values = dialog.values()
        self.assertEqual(values["username"], "themalcolm3")
        self.assertEqual(values["password"], "hunter2")
        self.assertEqual(values["region"], "NA1")
        # No display name given, so it falls back to the username rather than
        # rendering a blank row.
        self.assertEqual(values["label"], "themalcolm3")

    # ------------------------------------------------------------ editing
    def _existing(self):
        return {
            "label": "Main", "username": "themalcolm3",
            "tagline": "DPM#Null", "region": "NA1",
            "password_enc": "should-never-be-read-by-the-ui",
        }

    def test_editing_never_shows_the_stored_password(self):
        dialog = self._new(account=self._existing())
        self.assertEqual(dialog.field_password.text(), "")

    def test_blank_password_when_editing_means_unchanged(self):
        dialog = self._new(account=self._existing())
        self.assertTrue(dialog.validate())
        # None is what edit_account treats as "do not touch this field".
        self.assertIsNone(dialog.values()["password"])

    def test_editing_can_still_set_a_new_password(self):
        dialog = self._new(account=self._existing())
        dialog.field_password.set_text("new-one")
        self.assertTrue(dialog.validate())
        self.assertEqual(dialog.values()["password"], "new-one")

    def test_editing_does_not_flag_the_accounts_own_username(self):
        dialog = self._new(
            account=self._existing(), existing_usernames=[]  # self excluded
        )
        self.assertTrue(dialog.validate())

    def test_prefills_existing_values(self):
        dialog = self._new(account=self._existing())
        self.assertEqual(dialog.field_label.text(), "Main")
        self.assertEqual(dialog.field_username.text(), "themalcolm3")
        self.assertEqual(dialog.field_tagline.text(), "DPM#Null")

    # ------------------------------------------------------------- fields
    def test_typing_clears_an_error_without_resubmitting(self):
        dialog = self._new()
        dialog.validate()
        self.assertTrue(dialog.field_username.has_error())
        dialog.field_username.set_text("t")
        self.assertFalse(dialog.field_username.has_error())

    def test_password_is_masked_until_revealed(self):
        from PySide6.QtWidgets import QLineEdit
        dialog = self._new()
        self.assertEqual(dialog.field_password.input.echoMode(), QLineEdit.Password)
        dialog.field_password.reveal.setChecked(True)
        self.assertEqual(dialog.field_password.input.echoMode(), QLineEdit.Normal)
        self.assertEqual(dialog.field_password.reveal.text(), "Hide")

    def test_only_the_password_field_gets_a_reveal_control(self):
        dialog = self._new()
        self.assertIsNone(dialog.field_username.reveal)
        self.assertIsNotNone(dialog.field_password.reveal)


class ConfirmModalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_destructive_confirm_is_not_the_enter_key_default(self):
        """Enter is what you press to dismiss things you did not read."""
        from ui.qt.components.modal import LLConfirmModal
        dialog = LLConfirmModal("Remove Main?", "It will be forgotten.", "Remove account")
        self.assertFalse(dialog.confirm_button.isDefault())
        self.assertTrue(dialog.cancel_button.isEnabled())

    def test_confirm_button_is_labelled_with_the_verb(self):
        from ui.qt.components.modal import LLConfirmModal
        dialog = LLConfirmModal("Remove Main?", "It will be forgotten.", "Remove account")
        self.assertEqual(dialog.confirm_button.text(), "Remove account")
        self.assertNotIn(dialog.confirm_button.text().lower(), ("ok", "yes"))


if __name__ == "__main__":
    unittest.main()
