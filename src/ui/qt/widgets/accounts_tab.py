"""
Accounts Tab — Riot Multi-Account Manager (UI/UX Master Plan §10).

Provides:
- Encrypted account credential storage with Windows DPAPI
- Account card list with region, summoner tag, and wallet summary
- One-click account switching and launch automation
- Add, Edit, Delete, and Reorder management
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.account_manager import AccountManager
from ui.qt.components.badge import LLBadge
from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.card import LLCard, LLSection, LLSeparator
from ui.qt.components.status import LLStatus, Tone
from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    BLUE_ACCENT,
    COLOR_DANGER,
    GOLD_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    GOLD_LIGHT,
    SURFACE_PANEL,
    SURFACE_PANEL_HOVER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.radii import RADIUS_MD, RADIUS_SM
from ui.qt.theme.spacing import CONTENT_MARGIN, CONTROL_HEIGHT_MD, SPACE_LG, SPACE_MD, SPACE_SM, SPACE_XS
from ui.qt.theme.typography import TEXT_BODY, TEXT_CAPTION, TEXT_PAGE_TITLE, TEXT_SECTION_TITLE


class AccountEditDialog(QDialog):
    """Dialog for creating or editing an account profile."""

    def __init__(
        self,
        account: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.account = account
        self.setWindowTitle("Edit Account" if account else "Add Account")
        self.setFixedWidth(380)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #0A1428;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        layout.setSpacing(SPACE_MD)

        title = QLabel("Edit Account" if account else "Add Riot Account", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=GOLD_LIGHT))
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(SPACE_SM)

        # Label
        grid.addWidget(QLabel("Display Label:", self), 0, 0)
        self.txt_label = QLineEdit(self)
        self.txt_label.setPlaceholderText("e.g. Main, Smurf, NA Account")
        self.txt_label.setFixedHeight(CONTROL_HEIGHT_MD)
        if account:
            self.txt_label.setText(account.get("label", ""))
        grid.addWidget(self.txt_label, 0, 1)

        # Username
        grid.addWidget(QLabel("Riot Username:", self), 1, 0)
        self.txt_username = QLineEdit(self)
        self.txt_username.setPlaceholderText("Riot login name")
        self.txt_username.setFixedHeight(CONTROL_HEIGHT_MD)
        if account:
            self.txt_username.setText(account.get("username", ""))
        grid.addWidget(self.txt_username, 1, 1)

        # Password
        grid.addWidget(QLabel("Password:", self), 2, 0)
        self.txt_password = QLineEdit(self)
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setPlaceholderText("Leave blank to keep existing" if account else "Riot password")
        self.txt_password.setFixedHeight(CONTROL_HEIGHT_MD)
        grid.addWidget(self.txt_password, 2, 1)

        # Tagline / Riot ID
        grid.addWidget(QLabel("Riot ID (Summoner#Tag):", self), 3, 0)
        self.txt_tagline = QLineEdit(self)
        self.txt_tagline.setPlaceholderText("e.g. Faker#KR1")
        self.txt_tagline.setFixedHeight(CONTROL_HEIGHT_MD)
        if account:
            self.txt_tagline.setText(account.get("tagline", ""))
        grid.addWidget(self.txt_tagline, 3, 1)

        # Region
        grid.addWidget(QLabel("Region:", self), 4, 0)
        self.txt_region = QLineEdit(self)
        self.txt_region.setPlaceholderText("NA1, EUW, KR, etc.")
        self.txt_region.setText(account.get("region", "NA1") if account else "NA1")
        self.txt_region.setFixedHeight(CONTROL_HEIGHT_MD)
        grid.addWidget(self.txt_region, 4, 1)

        layout.addLayout(grid)

        self.chk_default = QCheckBox("Set as default startup account", self)
        if account:
            self.chk_default.setChecked(bool(account.get("is_default", False)))
        layout.addWidget(self.chk_default)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACE_SM)
        btn_row.addStretch(1)

        btn_cancel = LLButton("Cancel", variant=ButtonVariant.SECONDARY, parent=self)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = LLButton("Save", variant=ButtonVariant.PRIMARY, parent=self)
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def get_data(self) -> Dict[str, Any]:
        return {
            "label": self.txt_label.text().strip() or self.txt_username.text().strip(),
            "username": self.txt_username.text().strip(),
            "password": self.txt_password.text().strip(),
            "tagline": self.txt_tagline.text().strip(),
            "region": self.txt_region.text().strip() or "NA1",
            "is_default": self.chk_default.isChecked(),
        }


class QtAccountsTab(QWidget):
    """Riot account management and fast login switcher tab."""

    def __init__(
        self,
        container=None,
        view_model=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.container = container
        self.lcu = getattr(container, "lcu", None) if container else None
        self.acct_mgr: Optional[AccountManager] = None

        if hasattr(container, "account_manager") and container.account_manager:
            self.acct_mgr = container.account_manager
        else:
            self.acct_mgr = AccountManager(lcu=self.lcu)

        self._setup_ui()
        self.refresh_accounts()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        # Header
        header = QHBoxLayout()
        title = QLabel("Account Switcher", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        header.addWidget(title)
        header.addStretch(1)

        self.btn_detect = LLButton("Detect Active Client", variant=ButtonVariant.SECONDARY, parent=self)
        self.btn_detect.clicked.connect(self._on_detect_active)
        header.addWidget(self.btn_detect)

        self.btn_add = LLButton("+ Add Account", variant=ButtonVariant.PRIMARY, size=ButtonSize.MD, parent=self)
        self.btn_add.clicked.connect(self._on_add_account)
        header.addWidget(self.btn_add)

        root.addLayout(header)

        # Status Summary Card
        status_card = LLCard(parent=self)
        status_row = QHBoxLayout()
        self.status_readout = LLStatus("Ready", Tone.NEUTRAL, "Manage your saved Riot accounts", parent=status_card)
        status_row.addWidget(self.status_readout)
        status_row.addStretch(1)
        status_card.add_layout(status_row)
        root.addWidget(status_card)

        # Scrollable Account Cards Holder
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.cards_holder = QWidget()
        self.cards_holder.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_holder)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(SPACE_MD)

        scroll.setWidget(self.cards_holder)
        root.addWidget(scroll, 1)

        self.lbl_log = QLabel("", self)
        self.lbl_log.setStyleSheet(TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;")
        root.addWidget(self.lbl_log)

    def refresh_accounts(self) -> None:
        """Render account cards from AccountManager."""
        # Clear existing cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        accounts = self.acct_mgr.get_accounts() if self.acct_mgr else []
        active_idx = self.acct_mgr.get_active_index() if self.acct_mgr else -1

        if not accounts:
            empty_card = LLCard(parent=self.cards_holder)
            empty_lbl = QLabel(
                "No accounts saved yet.\n\nClick '+ Add Account' or 'Detect Active Client' to register your Riot credentials.",
                empty_card,
            )
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet(TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent; padding: 24px;")
            empty_card.add_widget(empty_lbl)
            self.cards_layout.addWidget(empty_card)
            self.cards_layout.addStretch(1)
            return

        for idx, acct in enumerate(accounts):
            card = self._create_account_card(idx, acct, is_active=(idx == active_idx))
            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch(1)
        self.status_readout.set_status("Ready", Tone.SUCCESS if active_idx >= 0 else Tone.NEUTRAL, f"{len(accounts)} accounts configured")

    def _create_account_card(self, idx: int, acct: Dict[str, Any], is_active: bool) -> QWidget:
        card = LLCard(parent=self.cards_holder)
        layout = QHBoxLayout()
        layout.setSpacing(SPACE_MD)

        # Account Info Left Column
        info_col = QVBoxLayout()
        info_col.setSpacing(SPACE_XS)

        title_row = QHBoxLayout()
        title_row.setSpacing(SPACE_SM)

        lbl_name = QLabel(acct.get("label") or acct.get("username", "Account"), card)
        lbl_name.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {GOLD_LIGHT}; background: transparent;")
        title_row.addWidget(lbl_name)

        if is_active:
            title_row.addWidget(LLBadge("Active", Tone.SUCCESS, parent=card))
        if acct.get("is_default"):
            title_row.addWidget(LLBadge("Default", Tone.WARNING, parent=card))

        title_row.addStretch(1)
        info_col.addLayout(title_row)

        details = []
        if acct.get("tagline"):
            details.append(acct.get("tagline"))
        if acct.get("region"):
            details.append(f"[{acct.get('region')}]")

        wallet = acct.get("wallet", {})
        if wallet.get("be") or wallet.get("rp"):
            details.append(f"{wallet.get('be', 0)} BE • {wallet.get('rp', 0)} RP")

        lbl_details = QLabel(" • ".join(details) if details else acct.get("username", ""), card)
        lbl_details.setStyleSheet(TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;")
        info_col.addWidget(lbl_details)

        layout.addLayout(info_col, 1)

        # Action Buttons Right
        btn_box = QHBoxLayout()
        btn_box.setSpacing(SPACE_SM)

        btn_login = LLButton("Switch / Login", variant=ButtonVariant.PRIMARY, size=ButtonSize.SM, parent=card)
        btn_login.clicked.connect(lambda _, i=idx: self._on_login_account(i))
        btn_box.addWidget(btn_login)

        btn_edit = LLButton("Edit", variant=ButtonVariant.SECONDARY, size=ButtonSize.SM, parent=card)
        btn_edit.clicked.connect(lambda _, i=idx, a=acct: self._on_edit_account(i, a))
        btn_box.addWidget(btn_edit)

        btn_delete = LLButton("Delete", variant=ButtonVariant.DANGER, size=ButtonSize.SM, parent=card)
        btn_delete.clicked.connect(lambda _, i=idx: self._on_delete_account(i))
        btn_box.addWidget(btn_delete)

        layout.addLayout(btn_box)
        card.add_layout(layout)
        return card

    def _on_detect_active(self) -> None:
        if not self.acct_mgr:
            return
        self.status_readout.set_status("Scanning", Tone.WARNING, "Detecting active Riot Client / LCU session...")

        def worker():
            idx = self.acct_mgr.detect_active_account()
            QTimer.singleShot(0, self.refresh_accounts)

        threading.Thread(target=worker, daemon=True).start()

    def _on_add_account(self) -> None:
        dlg = AccountEditDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if self.acct_mgr:
                idx = self.acct_mgr.add_account(
                    label=data["label"],
                    username=data["username"],
                    password=data["password"],
                    tagline=data["tagline"],
                    region=data["region"],
                )
                if data["is_default"]:
                    self.acct_mgr.set_default_account(idx)
                self.refresh_accounts()

    def _on_edit_account(self, idx: int, account: Dict[str, Any]) -> None:
        dlg = AccountEditDialog(account=account, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if self.acct_mgr:
                pwd = data["password"] if data["password"] else None
                self.acct_mgr.edit_account(
                    idx,
                    label=data["label"],
                    username=data["username"],
                    password=pwd,
                    tagline=data["tagline"],
                    region=data["region"],
                    is_default=data["is_default"],
                )
                self.refresh_accounts()

    def _on_delete_account(self, idx: int) -> None:
        if self.acct_mgr:
            self.acct_mgr.delete_account(idx)
            self.refresh_accounts()

    def _on_login_account(self, idx: int) -> None:
        if not self.acct_mgr:
            return
        self.status_readout.set_status("Logging in", Tone.WARNING, f"Automating login for account #{idx + 1}...")

        def log_cb(msg):
            QTimer.singleShot(0, lambda: self.lbl_log.setText(f"[Login] {msg}"))

        def comp_cb(success):
            QTimer.singleShot(0, lambda: self._on_login_done(success))

        self.acct_mgr.login_account(idx, log_func=log_cb, completion_func=comp_cb)

    def _on_login_done(self, success: bool) -> None:
        tone = Tone.SUCCESS if success else Tone.DANGER
        status_text = "Login Completed" if success else "Login Failed"
        detail = "Successfully switched account" if success else "Could not complete automated login"
        self.status_readout.set_status(status_text, tone, detail)
        self.refresh_accounts()
