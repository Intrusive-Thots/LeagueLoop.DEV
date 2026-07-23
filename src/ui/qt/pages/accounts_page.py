"""
PySide6 Accounts Page Component
Manages multiple Riot accounts, credentials, and one-click account switching.
"""
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, QMetaObject, Slot, Q_ARG

from ui.qt.widgets import ScrollableList, make_card, make_button
from ui.qt.theme import get_theme_color
from services.account_manager import get_account_manager
from services.league_service import get_league_service
from ui.qt.widgets.toast import ToastManager
from utils.logger import Logger
from utils.thread_utils import run_in_background


class QtAccountCard(QFrame):
    """Card representing a single saved Riot account with quick login and management controls."""
    
    def __init__(self, parent=None, account_data=None, index=0, on_login=None, on_delete=None):
        super().__init__(parent)
        self.account_data = account_data or {}
        self.index = index
        self.on_login = on_login
        self.on_delete = on_delete
        
        self.setFixedHeight(54)
        self.setStyleSheet("""
            QFrame {
                background-color: #0A1424;
                border: 1px solid #1E2D42;
                border-radius: 6px;
            }
            QFrame:hover {
                background-color: #121F33;
                border-color: #C8AA6E;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)
        
        # Account label & username
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        label_text = self.account_data.get("label") or self.account_data.get("username") or f"Account #{index + 1}"
        username_text = self.account_data.get("username", "")
        region = self.account_data.get("region", "NA")
        
        lbl_name = QLabel(label_text, self)
        lbl_name.setStyleSheet("color: #F8F6F0; font-weight: bold; font-size: 12px;")
        info_layout.addWidget(lbl_name)
        
        lbl_sub = QLabel(f"User: {username_text} | Region: {region.upper()}", self)
        lbl_sub.setStyleSheet("color: #A8B8CC; font-size: 10px;")
        info_layout.addWidget(lbl_sub)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # Action Buttons
        self.btn_switch = QPushButton("LOGIN", self)
        self.btn_switch.setFixedSize(70, 26)
        self.btn_switch.setCursor(Qt.PointingHandCursor)
        self.btn_switch.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #DCC186, stop:1 #C8AA6E);
                color: #080E18;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #EADBBA;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #EBE0C2;
            }
        """)
        self.btn_switch.clicked.connect(self._handle_login)
        layout.addWidget(self.btn_switch)
        
        self.btn_copy = QPushButton("📋", self)
        self.btn_copy.setToolTip("Copy Username")
        self.btn_copy.setFixedSize(26, 26)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background: #0E1826;
                color: #C8AA6E;
                font-size: 11px;
                border: 1px solid #1E2D42;
                border-radius: 4px;
            }
            QPushButton:hover {
                border-color: #C8AA6E;
                background: #142236;
            }
        """)
        self.btn_copy.clicked.connect(self._handle_copy)
        layout.addWidget(self.btn_copy)

        self.btn_del = QPushButton("✕", self)
        self.btn_del.setFixedSize(26, 26)
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #E74C3C;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid rgba(231,76,60,0.3);
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(231,76,60,0.2);
                border-color: #E74C3C;
            }
        """)
        self.btn_del.clicked.connect(self._handle_delete)
        layout.addWidget(self.btn_del)

    def _handle_copy(self):
        from PySide6.QtWidgets import QApplication
        username = self.account_data.get("username", "")
        if username:
            QApplication.clipboard().setText(username)
            toast = ToastManager.get_instance()
            if toast:
                toast.show(f"Copied username '{username}'", icon="📋", theme="info")

    def _handle_login(self):
        if self.on_login:
            self.on_login(self.index, self.account_data)

    def _handle_delete(self):
        if self.on_delete:
            self.on_delete(self.index, self.account_data)


class AccountsPage(QWidget):
    """The PySide6 Multi-Account Manager Page."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.acct_mgr = get_account_manager()
        self.league_service = get_league_service()
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 14, 14, 14)
        self.main_layout.setSpacing(10)
        
        self.scroll = ScrollableList(self)
        self.main_layout.addWidget(self.scroll)
        
        self.setup_ui()

    def setup_ui(self):
        # ── 1. ACTIVE SESSION CARD ──
        self.card_active = make_card(title="CURRENT ACTIVE ACCOUNT")
        
        self.lbl_sec_badge = QLabel("🔒 DPAPI ENCRYPTED  |  Secured locally at %LOCALAPPDATA%\\LeagueLoop\\accounts.json", self)
        self.lbl_sec_badge.setStyleSheet("color: #2ECC71; font-size: 10px; font-weight: bold; margin-bottom: 2px;")
        self.card_active.add_widget(self.lbl_sec_badge)

        self.lbl_active_name = QLabel("Detecting active League Client session...", self)
        self.lbl_active_name.setStyleSheet("color: #F8F6F0; font-weight: bold; font-size: 13px;")
        self.card_active.add_widget(self.lbl_active_name)
        
        self.lbl_active_details = QLabel("Connect League Client to automatically identify summoner profile.", self)
        self.lbl_active_details.setStyleSheet("color: #A8B8CC; font-size: 11px;")
        self.card_active.add_widget(self.lbl_active_details)
        
        btn_detect = make_button(self, text="DETECT CURRENT CLIENT SESSION", style="secondary")
        btn_detect.clicked.connect(self._detect_session)
        self.card_active.add_widget(btn_detect)
        
        self.scroll.add_widget(self.card_active)
        
        # ── 2. ADD NEW ACCOUNT CARD ──
        self.card_add = make_card(title="ADD RIOT ACCOUNT")
        
        form_row = QHBoxLayout()
        form_row.setSpacing(8)
        
        self.input_label = QLineEdit(self)
        self.input_label.setPlaceholderText("Account Label (e.g. Smurf 1)")
        form_row.addWidget(self.input_label)
        
        self.input_user = QLineEdit(self)
        self.input_user.setPlaceholderText("Riot Username")
        form_row.addWidget(self.input_user)
        
        self.input_pass = QLineEdit(self)
        self.input_pass.setPlaceholderText("Riot Password")
        self.input_pass.setEchoMode(QLineEdit.Password)
        form_row.addWidget(self.input_pass)
        
        form_widget = QWidget(self)
        form_widget.setLayout(form_row)
        self.card_add.add_widget(form_widget)
        
        btn_save = make_button(self, text="SAVE ACCOUNT", style="primary")
        btn_save.clicked.connect(self._save_new_account)
        self.card_add.add_widget(btn_save)
        
        self.scroll.add_widget(self.card_add)
        
        # ── 3. SAVED ACCOUNTS LIST CARD ──
        self.card_saved = make_card(title="SAVED ACCOUNTS")
        self.accounts_container = QWidget(self)
        self.accounts_layout = QVBoxLayout(self.accounts_container)
        self.accounts_layout.setContentsMargins(0, 0, 0, 0)
        self.accounts_layout.setSpacing(6)
        
        self.card_saved.add_widget(self.accounts_container)
        self.scroll.add_widget(self.card_saved)
        
        self._refresh_accounts_list()
        self._detect_session()

    def _refresh_accounts_list(self):
        # Clear existing
        while self.accounts_layout.count() > 0:
            item = self.accounts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        accounts = self.acct_mgr.get_accounts() if hasattr(self.acct_mgr, "get_accounts") else []
        if not accounts:
            lbl_empty = QLabel("No saved Riot accounts yet. Use the form above to add an account.", self)
            lbl_empty.setStyleSheet("color: #A8B8CC; font-size: 11px; font-style: italic;")
            self.accounts_layout.addWidget(lbl_empty)
            return
            
        for idx, acct in enumerate(accounts):
            card = QtAccountCard(
                self,
                account_data=acct,
                index=idx,
                on_login=self._switch_to_account,
                on_delete=self._delete_account
            )
            self.accounts_layout.addWidget(card)

    def _save_new_account(self):
        label = self.input_label.text().strip()
        user = self.input_user.text().strip()
        pwd = self.input_pass.text().strip()
        
        if not user or not pwd:
            ToastManager.get_instance().show("Username and password required", icon="⚠️", theme="error")
            return
            
        if hasattr(self.acct_mgr, "add_account"):
            self.acct_mgr.add_account(username=user, password=pwd, label=label or user)
            
        self.input_label.clear()
        self.input_user.clear()
        self.input_pass.clear()
        
        ToastManager.get_instance().show("Account Saved Successfully", icon="💾", theme="success")
        self._refresh_accounts_list()

    def _switch_to_account(self, idx, acct):
        username = acct.get("username", "")
        ToastManager.get_instance().show(f"Logging in as {username}...", icon="🔑", theme="info")
        
        def task():
            if hasattr(self.acct_mgr, "login_account"):
                self.acct_mgr.login_account(
                    idx,
                    log_func=lambda msg: Logger.info("Accounts", msg),
                    completion_func=lambda ok: ToastManager.get_instance().show(
                        f"Logged in as {username}" if ok else "Account switch failed",
                        icon="✅" if ok else "⚠️",
                        theme="success" if ok else "error"
                    )
                )
            else:
                ToastManager.get_instance().show(f"Account: {username}", icon="ℹ️", theme="info")
                
        run_in_background(task)

    def _delete_account(self, idx, acct):
        if hasattr(self.acct_mgr, "delete_account"):
            self.acct_mgr.delete_account(idx)
        ToastManager.get_instance().show("Account Removed", icon="🗑️", theme="warning")
        self._refresh_accounts_list()

    def _detect_session(self):
        def task():
            if hasattr(self.league_service, "lcu") and self.league_service.lcu and self.league_service.lcu.is_connected:
                res = self.league_service.lcu.request("GET", "/lol-summoner/v1/current-summoner", silent=True)
                if res and res.status_code == 200:
                    data = res.json()
                    name = data.get("displayName") or data.get("gameName") or "Active Player"
                    lvl = data.get("summonerLevel", 30)
                    QMetaObject.invokeMethod(
                        self,
                        "_update_session_ui",
                        Qt.QueuedConnection,
                        Q_ARG(str, f"Summoner: {name} (Lvl {lvl})"),
                        Q_ARG(str, "Connected to League Client Update API.")
                    )
                    return
            QMetaObject.invokeMethod(
                self,
                "_update_session_ui",
                Qt.QueuedConnection,
                Q_ARG(str, "League Client Disconnected"),
                Q_ARG(str, "Launch League of Legends to detect active account.")
            )
        run_in_background(task)

    @Slot(str, str)
    def _update_session_ui(self, title, details):
        self.lbl_active_name.setText(title)
        self.lbl_active_details.setText(details)
