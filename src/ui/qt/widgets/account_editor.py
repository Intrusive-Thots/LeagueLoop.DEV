"""
Add / edit a stored account (UI/UX Master Plan §25, §55).

The one screen in LeagueLoop that handles a password, so it is explicit about
what it stores and where. Two things it deliberately does NOT do:

* It never shows an existing password back to you. Editing leaves the field
  blank with "leave blank to keep the current password" — so a stray keypress
  cannot silently truncate a saved credential, and a shoulder-surfer gets
  nothing from opening the editor.
* It never guesses which name you meant. The Riot *login* username and the
  in-game Riot ID are different strings, and conflating them is the single
  most common reason a sign-in fails with "bad credentials" when the password
  is fine — so they are separate fields with explicit helper text.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtWidgets import QWidget

from ui.qt.components.field import LLTextField
from ui.qt.components.modal import LLModal

# Riot shard codes. Not exhaustive by design — the field accepts free text so
# a new shard does not require an app update.
COMMON_REGIONS = (
    "NA1", "EUW1", "EUN1", "KR", "BR1", "LA1", "LA2",
    "OC1", "TR1", "RU", "JP1", "PH2", "SG2", "TH2", "TW2", "VN2",
)


class AccountEditorModal(LLModal):
    """Create a new account, or edit an existing one in place."""

    def __init__(
        self,
        account: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
        existing_usernames: Optional[list] = None,
    ):
        editing = account is not None
        super().__init__(
            "Edit account" if editing else "Add account",
            parent=parent,
            confirm_text="Save changes" if editing else "Add account",
        )
        self.editing = editing
        self._existing = {
            (u or "").strip().lower() for u in (existing_usernames or []) if u
        }

        acct = account or {}

        self.field_label = LLTextField(
            "Display name",
            placeholder="Main",
            helper="What you want to see in the list. Only you see this.",
            parent=self,
        )
        self.field_label.set_text(str(acct.get("label") or ""))
        self.add_widget(self.field_label)

        self.field_username = LLTextField(
            "Riot login username",
            placeholder="the name you type to sign in",
            helper="Your sign-in username — not your in-game name.",
            parent=self,
        )
        self.field_username.set_text(str(acct.get("username") or ""))
        self.add_widget(self.field_username)

        self.field_password = LLTextField(
            "Password",
            placeholder="leave blank to keep the current password" if editing else "",
            helper=(
                "Blank keeps the password already saved."
                if editing
                else "Encrypted with Windows DPAPI, tied to your Windows user."
            ),
            password=True,
            parent=self,
        )
        self.add_widget(self.field_password)

        self.field_tagline = LLTextField(
            "Riot ID",
            placeholder="Name#TAG",
            helper="Optional. Your in-game name, shown in the list.",
            parent=self,
        )
        self.field_tagline.set_text(str(acct.get("tagline") or ""))
        self.add_widget(self.field_tagline)

        self.field_region = LLTextField(
            "Region (optional)",
            placeholder="NA1",
            helper="Shown on the account row. Signing in does not use it yet.",
            parent=self,
        )
        # No "NA1" default. Nothing reads this field, so filling it in for the
        # user meant every account carried an invented shard.
        self.field_region.set_text(str(acct.get("region") or ""))
        self.add_widget(self.field_region)

        for field in self._fields():
            field.returned.connect(self._on_confirm)

        self.field_label.focus()

    def _fields(self):
        return (
            self.field_label,
            self.field_username,
            self.field_password,
            self.field_tagline,
            self.field_region,
        )

    # ---------------------------------------------------------- validation
    def validate(self) -> bool:
        """
        Report every problem at once, and focus the first one.

        Validating one field at a time turns a three-mistake form into three
        round trips (§55).
        """
        for field in self._fields():
            field.clear_error()

        first_bad = None

        username = self.field_username.text().strip()
        if not username:
            self.field_username.set_error("A login username is required.")
            first_bad = first_bad or self.field_username
        elif "#" in username:
            # Extremely common paste error, and it fails much later with a
            # message that blames the password.
            self.field_username.set_error(
                "That looks like a Riot ID. The login username has no # in it — "
                "put the Riot ID in the field below."
            )
            first_bad = first_bad or self.field_username
        elif username.lower() in self._existing:
            self.field_username.set_error("That username is already stored.")
            first_bad = first_bad or self.field_username

        if not self.editing and not self.field_password.text():
            self.field_password.set_error("A password is required to sign in.")
            first_bad = first_bad or self.field_password

        tagline = self.field_tagline.text().strip()
        if tagline and "#" not in tagline:
            self.field_tagline.set_error("A Riot ID looks like Name#TAG.")
            first_bad = first_bad or self.field_tagline

        if first_bad is not None:
            first_bad.focus()
            return False
        return True

    # -------------------------------------------------------------- result
    def values(self) -> Dict[str, Any]:
        """
        What the user entered.

        `password` is None when editing and left blank — meaning "unchanged" —
        which is distinct from "" (an empty password). `edit_account` only
        applies non-None fields, so None is exactly the right signal.
        """
        password = self.field_password.text()
        return {
            "label": self.field_label.text().strip()
            or self.field_username.text().strip(),
            "username": self.field_username.text().strip(),
            "password": password if password else (None if self.editing else ""),
            "tagline": self.field_tagline.text().strip(),
            "region": self.field_region.text().strip().upper(),
        }
