"""
Accounts (UI/UX Master Plan §25).

"Do not hide account switching entirely under Settings." The active account
is always visible at the top, switching is one click, and the default account
is set from the same list rather than a separate screen.

Credential entry deliberately lives in the existing account tool for now -
this screen manages *which* stored account is active, not secrets.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.badge import LLBadge
from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.components.card import LLCard, LLSeparator
from ui.qt.components.status import LLStatus, Tone
from ui.qt.theme.colors import TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_LG, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import (
    TEXT_BODY,
    TEXT_BODY_STRONG,
    TEXT_CAPTION,
    TEXT_PAGE_TITLE,
)


class QtAccountsTab(QWidget):
    """Stored account list with an always-visible active account."""

    switch_requested = Signal(int)

    def __init__(
        self,
        container=None,
        view_model=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.container = container
        self.view_model = view_model
        self.accounts_service = (
            getattr(container, "account_manager", None) if container else None
        )

        self._rows: List[QWidget] = []
        self._buttons: List[Any] = []
        self._switching = False
        self._handles = []

        self._setup_ui()
        self.refresh()
        self._subscribe_to_switches()

        if view_model is not None:
            view_model.state_changed.connect(self._render_active)
            self._render_active()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        title = QLabel("Accounts", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        root.addWidget(title)

        # --- active account, always visible (§25) --------------------------
        self.active_card = LLCard(title="Active account", parent=self)
        self.active_status = LLStatus(
            "No account signed in", Tone.NEUTRAL, parent=self.active_card
        )
        self.active_card.add_widget(self.active_status)
        root.addWidget(self.active_card)

        # --- stored accounts ------------------------------------------------
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setSpacing(SPACE_MD)

        self.list_card = LLCard(title="Stored accounts", parent=holder)
        holder_layout.addWidget(self.list_card)

        note = QLabel(
            "Adding or editing account credentials is not available in this "
            "interface yet - use the existing Accounts tool for that.",
            holder,
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        holder_layout.addWidget(note)
        holder_layout.addStretch(1)

        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

    # ------------------------------------------------------------- events
    def _subscribe_to_switches(self) -> None:
        """
        Follow the switcher's progress so the screen says what is happening.

        The old flow reported through a log callback the UI never saw, so a
        switch looked like nothing at all until it finished (or didn't).
        """
        try:
            from core.events import EventBus  # type: ignore
            from services.accounts.results import (  # type: ignore
                EVENT_SWITCH_FINISHED,
                EVENT_SWITCH_PROGRESS,
                EVENT_SWITCH_STARTED,
            )
        except Exception:
            return

        self._on_started_ref = self._on_switch_started
        self._on_progress_ref = self._on_switch_progress
        self._on_finished_ref = self._on_switch_finished
        for channel, handler in (
            (EVENT_SWITCH_STARTED, self._on_started_ref),
            (EVENT_SWITCH_PROGRESS, self._on_progress_ref),
            (EVENT_SWITCH_FINISHED, self._on_finished_ref),
        ):
            try:
                self._handles.append(EventBus.on(channel, handler))
            except Exception:
                pass

    def _set_busy(self, busy: bool) -> None:
        self._switching = busy
        for button in self._buttons:
            try:
                button.setEnabled(not busy and button.property("llEnabled") is not False)
            except Exception:
                pass

    def _on_switch_started(self, progress=None, *_a, **_kw) -> None:
        self._set_busy(True)
        label = getattr(progress, "account_label", "") or ""
        self.active_status.set_status(
            "Switching" + (" to {}".format(label) if label else ""),
            Tone.INFO, getattr(progress, "message", ""),
        )

    def _on_switch_progress(self, progress=None, *_a, **_kw) -> None:
        message = getattr(progress, "message", "")
        if message:
            self.active_status.set_status(
                "Switching", Tone.INFO, message
            )

    def _on_switch_finished(self, result=None, *_a, **_kw) -> None:
        self._set_busy(False)
        if result is None:
            self.refresh()
            return

        ok = bool(getattr(result, "ok", False))
        message = getattr(result, "message", "")
        outcome = getattr(getattr(result, "outcome", None), "value", "")

        if ok:
            tone = Tone.SUCCESS
        elif outcome == "needs_2fa":
            tone = Tone.WARNING
        else:
            tone = Tone.DANGER

        self.active_status.set_status(
            message or ("Signed in" if ok else "Switch failed"), tone,
            getattr(result, "detail", "") or "",
        )
        self.refresh()

    def closeEvent(self, event) -> None:
        for handle in self._handles:
            try:
                handle.dispose()
            except Exception:
                pass
        self._handles.clear()
        super().closeEvent(event)

    # -------------------------------------------------------------- render
    def _render_active(self, *_args) -> None:
        if self.view_model is None or self._switching:
            # A switch in flight owns this line; don't overwrite its progress.
            return
        client = self.view_model.state.client
        if client.connected and client.summoner_name:
            self.active_status.set_status(client.summoner_name, Tone.SUCCESS, "Connected")
        elif client.connected:
            self.active_status.set_status("Connected", Tone.SUCCESS, "Signed in")
        else:
            self.active_status.set_status(
                "No account signed in", Tone.NEUTRAL,
                "Launch the League Client or switch to a stored account",
            )

    def _accounts(self) -> List[Dict[str, Any]]:
        getter = getattr(self.accounts_service, "get_accounts", None)
        if not callable(getter):
            return []
        try:
            return list(getter() or [])
        except Exception:
            return []

    def _active_index(self) -> int:
        getter = getattr(self.accounts_service, "get_active_index", None)
        if callable(getter):
            try:
                return int(getter())
            except Exception:
                pass
        return -1

    def _default_index(self) -> int:
        getter = getattr(self.accounts_service, "get_default_account_index", None)
        if callable(getter):
            try:
                return int(getter())
            except Exception:
                pass
        return -1

    def refresh(self) -> None:
        # Clear everything below the card title.
        self._buttons = []
        layout = self.list_card.body
        while layout.count() > 1:
            item = layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows = []

        accounts = self._accounts()
        if not accounts:
            empty = QLabel(
                "No stored accounts.\n\n"
                "Accounts you add appear here so you can switch between them.",
                self.list_card,
            )
            empty.setWordWrap(True)
            empty.setStyleSheet(
                TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
            )
            self.list_card.add_widget(empty)
            return

        active = self._active_index()
        default = self._default_index()

        for index, account in enumerate(accounts):
            if index:
                self.list_card.add_widget(LLSeparator(parent=self.list_card))
            self.list_card.add_widget(
                self._account_row(index, account, index == active, index == default)
            )

    def _account_row(
        self, index: int, account: Dict[str, Any], is_active: bool, is_default: bool
    ) -> QWidget:
        row = QWidget(self.list_card)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(SPACE_SM)

        label = str(
            account.get("label") or account.get("username") or "Account {}".format(index + 1)
        )
        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        name = QLabel(label, row)
        name.setStyleSheet(TEXT_BODY_STRONG.qss(color=TEXT_PRIMARY))
        text_col.addWidget(name)

        region = str(account.get("region") or "")
        tagline = str(account.get("tagline") or "")
        detail_text = " - ".join(p for p in (tagline, region) if p)
        if detail_text:
            detail = QLabel(detail_text, row)
            detail.setStyleSheet(
                TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
            )
            text_col.addWidget(detail)

        layout.addLayout(text_col, 1)

        if is_active:
            layout.addWidget(LLBadge("Active", Tone.SUCCESS, parent=row))
        if is_default:
            layout.addWidget(LLBadge("Default", Tone.ACCENT, parent=row))

        btn_default = LLButton(
            "Set default", variant=ButtonVariant.GHOST, size=ButtonSize.SM, parent=row
        )
        btn_default.setEnabled(not is_default)
        btn_default.clicked.connect(lambda _c, i=index: self._on_set_default(i))
        layout.addWidget(btn_default)

        btn_switch = LLButton(
            "Switch", variant=ButtonVariant.SECONDARY, size=ButtonSize.SM, parent=row
        )
        btn_switch.setEnabled(not is_active and self.accounts_service is not None)
        btn_switch.clicked.connect(lambda _c, i=index: self._on_switch(i))
        layout.addWidget(btn_switch)

        self._buttons.extend((btn_default, btn_switch))
        self._rows.append(row)
        return row

    # -------------------------------------------------------------- actions
    def _on_set_default(self, index: int) -> None:
        setter = getattr(self.accounts_service, "set_default_account", None)
        if callable(setter):
            try:
                setter(index)
            except Exception:
                pass
        self.refresh()

    def _on_switch(self, index: int) -> None:
        """
        Sign into a stored account.

        Goes through `login_account`, which now runs the full switch sequence
        (sign out, authenticate via the client API, verify) on a worker
        thread. Progress and the typed outcome arrive back as events.
        """
        if self._switching:
            return
        self.switch_requested.emit(index)
        login = getattr(self.accounts_service, "login_account", None)
        if callable(login):
            self._set_busy(True)
            try:
                login(index)
            except Exception:
                self._set_busy(False)
