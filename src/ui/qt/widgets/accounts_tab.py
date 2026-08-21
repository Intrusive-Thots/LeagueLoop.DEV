"""
Accounts (UI/UX Master Plan §25).

"Do not hide account switching entirely under Settings." The active account
is always visible at the top, switching is one click, and the default account
is set from the same list rather than a separate screen.

Accounts are added, edited and removed here too. Sending people to a
different tool to type a password, then back here to use it, was the kind of
split that makes a feature feel unfinished.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
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
from ui.qt.components.modal import LLConfirmModal
from ui.qt.components.status import LLStatus, Tone
from ui.qt.widgets.account_editor import AccountEditorModal
from ui.qt.theme.colors import TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_LG, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import (
    TEXT_BODY,
    TEXT_BODY_STRONG,
    TEXT_CAPTION,
    TEXT_PAGE_TITLE,
)


class _DetectSignals(QObject):
    finished = Signal()


class _DetectTask(QRunnable):
    """
    Ask the account manager who is signed in, off the GUI thread.

    Detection talks to two local HTTP APIs; on a cold Riot Client that is
    hundreds of milliseconds, which is a visible freeze if done inline.
    """

    def __init__(self, service, signals: _DetectSignals):
        super().__init__()
        self._service = service
        self._signals = signals

    def run(self) -> None:
        try:
            detect = getattr(self._service, "detect_active_account", None)
            if callable(detect):
                detect()
        except Exception:
            pass
        finally:
            try:
                self._signals.finished.emit()
            except RuntimeError:
                # The tab was destroyed while we were working.
                pass


class QtAccountsTab(QWidget):
    """Stored account list with an always-visible active account."""

    switch_requested = Signal(int)

    # EventBus dispatches from the switcher's worker thread. Qt widgets may
    # only be created, destroyed or restyled on the GUI thread, and `refresh()`
    # rebuilds the whole list. Bouncing every bus callback through a signal
    # gets it onto the GUI thread (Qt auto-queues cross-thread connections).
    # Doing the work inline is why the stored-account list came back empty
    # after a failed switch.
    _switch_started = Signal(object)
    _switch_progress = Signal(object)
    _switch_finished = Signal(object)

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

        self._switch_started.connect(self._apply_switch_started)
        self._switch_progress.connect(self._apply_switch_progress)
        self._switch_finished.connect(self._apply_switch_finished)

        self._detect_signals = _DetectSignals(self)
        self._detect_signals.finished.connect(self.refresh)

        self._setup_ui()
        self.refresh()
        self._subscribe_to_switches()
        self.detect()

        if view_model is not None:
            view_model.state_changed.connect(self._render_active)
            self._render_active()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        header = QHBoxLayout()
        header.setSpacing(SPACE_SM)

        title = QLabel("Accounts", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        header.addWidget(title)
        header.addStretch(1)

        self.btn_add = LLButton(
            "Add account", variant=ButtonVariant.PRIMARY, size=ButtonSize.SM, parent=self
        )
        self.btn_add.clicked.connect(self._on_add)
        self.btn_add.setEnabled(self.accounts_service is not None)
        header.addWidget(self.btn_add)

        root.addLayout(header)

        # --- active account, always visible (§25) --------------------------
        self.active_card = LLCard(title="Active account", parent=self)
        self.active_status = LLStatus(
            "No account signed in", Tone.NEUTRAL, parent=self.active_card
        )
        self.active_card.add_widget(self.active_status)
        root.addWidget(self.active_card)

        # --- signed in, but not stored (§54) --------------------------------
        # Detection used to fix this by silently inserting an account with no
        # password and the username "Update Username". Asking is better than
        # a row the user did not create and cannot use.
        self.unknown_card = LLCard(title="Signed in as an unsaved account", parent=self)
        self.unknown_label = QLabel("", self.unknown_card)
        self.unknown_label.setWordWrap(True)
        self.unknown_label.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.unknown_card.add_widget(self.unknown_label)

        unknown_row = QHBoxLayout()
        unknown_row.addStretch(1)
        self.btn_save_unknown = LLButton(
            "Save this account",
            variant=ButtonVariant.SECONDARY,
            size=ButtonSize.SM,
            parent=self.unknown_card,
        )
        self.btn_save_unknown.clicked.connect(self._on_save_unrecognised)
        unknown_row.addWidget(self.btn_save_unknown)
        self.unknown_card.add_layout(unknown_row)

        self.unknown_card.setVisible(False)
        root.addWidget(self.unknown_card)

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
            "Passwords are encrypted with Windows DPAPI and are only readable "
            "by your Windows user account on this machine.",
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

        # These run on the worker thread and must do nothing but re-emit.
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
        """
        Lock the list while a switch is in flight.

        Un-busying restores each button's *designed* state rather than
        enabling everything: "Switch" on the active account and "Set default"
        on the default one are deliberately disabled (§63 - disabled is a
        designed state), and a finished switch must not light them up.
        """
        self._switching = busy
        for button in self._buttons:
            try:
                if busy:
                    button.setEnabled(False)
                else:
                    button.setEnabled(bool(button.property("llBaseEnabled")))
            except Exception:
                pass

    # --- worker-thread entry points: re-emit only, touch nothing ----------
    def _on_switch_started(self, progress=None, *_a, **_kw) -> None:
        self._emit_safely(self._switch_started, progress)

    def _on_switch_progress(self, progress=None, *_a, **_kw) -> None:
        self._emit_safely(self._switch_progress, progress)

    def _on_switch_finished(self, result=None, *_a, **_kw) -> None:
        self._emit_safely(self._switch_finished, result)

    @staticmethod
    def _emit_safely(signal, payload) -> None:
        try:
            signal.emit(payload)
        except RuntimeError:
            # The tab was destroyed between the emit and the delivery.
            pass

    # --- GUI-thread slots: safe to build and destroy widgets --------------
    def _apply_switch_started(self, progress=None) -> None:
        self._set_busy(True)
        label = getattr(progress, "account_label", "") or ""
        self.active_status.set_status(
            "Switching" + (" to {}".format(label) if label else ""),
            Tone.INFO, getattr(progress, "message", ""),
        )

    def _apply_switch_progress(self, progress=None) -> None:
        message = getattr(progress, "message", "")
        if message:
            self.active_status.set_status(
                "Switching", Tone.INFO, message
            )

    def _apply_switch_finished(self, result=None) -> None:
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

    def _accounts(self) -> List[Tuple[int, Dict[str, Any]]]:
        """
        (stable index, account) pairs, in the order the user arranged them.

        The index is the account's position in the stored list — the same
        index `login_account`, `set_default_account` and the switcher expect.
        """
        # Stored order, not recency order.
        #
        # This used to render `get_accounts_display()`, which sorts by
        # `last_used`. The reorder arrows call `move_account()`, which changes
        # *stored* order — so pressing one swapped two rows in the file and the
        # screen re-sorted straight back. The arrows appeared to do nothing.
        # An order the user sets by hand must be the order they see.
        getter = getattr(self.accounts_service, "get_accounts", None)
        if not callable(getter):
            return []
        try:
            return list(enumerate(getter() or []))
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

    @staticmethod
    def _last_used_label(value) -> str:
        """
        "used 3 days ago", or "" when never.

        The list is ordered by hand now, so recency has to be *shown* rather
        than implied by position.
        """
        if not value:
            return "never used"
        try:
            from datetime import datetime

            when = datetime.fromisoformat(str(value))
        except Exception:
            return ""

        delta = datetime.now() - when
        days = delta.days
        if days < 0:
            return ""
        if days == 0:
            hours = delta.seconds // 3600
            if hours < 1:
                return "used just now"
            return "used {}h ago".format(hours)
        if days == 1:
            return "used yesterday"
        if days < 30:
            return "used {} days ago".format(days)
        months = days // 30
        return "used {} month{} ago".format(months, "" if months == 1 else "s")

    def _credentials_ok(self, index: int) -> bool:
        """
        True unless we can positively tell the credentials are unusable.

        Defaults to True when the service cannot answer: an unknown state must
        not be rendered as a problem the user then goes hunting for.
        """
        checker = getattr(self.accounts_service, "has_valid_credentials", None)
        if not callable(checker):
            return True
        try:
            return bool(checker(index))
        except Exception:
            return True

    def _default_index(self) -> int:
        getter = getattr(self.accounts_service, "get_default_account_index", None)
        if callable(getter):
            try:
                return int(getter())
            except Exception:
                pass
        return -1

    def detect(self) -> None:
        """Kick off background detection; `refresh()` runs when it lands."""
        if self.accounts_service is None:
            return
        try:
            QThreadPool.globalInstance().start(
                _DetectTask(self.accounts_service, self._detect_signals)
            )
        except Exception:
            pass

    def showEvent(self, event) -> None:
        # Re-check on every visit: the user may have signed in or out in the
        # Riot Client while looking at another screen.
        super().showEvent(event)
        if not self._switching:
            self.detect()

    def _unrecognised(self):
        getter = getattr(self.accounts_service, "get_unrecognised_identity", None)
        if not callable(getter):
            return None
        try:
            return getter() or None
        except Exception:
            return None

    def _render_unrecognised(self) -> None:
        identity = self._unrecognised()
        if not identity:
            self.unknown_card.setVisible(False)
            return

        name = identity.get("display_name") or identity.get("username") or "Someone"
        self.unknown_label.setText(
            "The Riot Client is signed in as {}, which is not in your saved "
            "accounts. Save it and LeagueLoop can switch back to it later "
            "without you retyping anything.".format(name)
        )
        self.unknown_card.setVisible(True)

    def _on_save_unrecognised(self) -> None:
        identity = self._unrecognised()
        if identity is None or self.accounts_service is None:
            return

        seed = {
            "username": identity.get("username") or "",
            "tagline": identity.get("tagline") or "",
            "label": identity.get("display_name") or "",
            "region": "NA1",
        }
        # Deliberately opened as an *add*, not an edit: there is no stored
        # password, and the point of asking is to collect one.
        dialog = AccountEditorModal(parent=self, existing_usernames=self._usernames())
        dialog.field_username.set_text(seed["username"])
        dialog.field_tagline.set_text(seed["tagline"])
        dialog.field_label.set_text(seed["label"])
        dialog.field_password.focus()
        if dialog.exec() != AccountEditorModal.Accepted:
            return

        values = dialog.values()
        adder = getattr(self.accounts_service, "add_account", None)
        if callable(adder):
            try:
                adder(
                    values["label"], values["username"], values["password"] or "",
                    values["tagline"], values["region"],
                )
            except Exception as exc:
                self.active_status.set_status(
                    "Could not add that account", Tone.DANGER, str(exc)
                )
                return
        self.refresh()

    def refresh(self) -> None:
        self._render_unrecognised()

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
            # An empty state names the next action rather than just reporting
            # emptiness (§54).
            empty = QLabel(
                "No stored accounts yet.\n\n"
                "Add one and LeagueLoop can sign you in and switch between "
                "accounts without you retyping anything.",
                self.list_card,
            )
            empty.setWordWrap(True)
            empty.setStyleSheet(
                TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
            )
            self.list_card.add_widget(empty)

            cta = LLButton(
                "Add your first account",
                variant=ButtonVariant.PRIMARY,
                size=ButtonSize.MD,
                parent=self.list_card,
            )
            cta.clicked.connect(self._on_add)
            cta.setEnabled(self.accounts_service is not None)
            self._buttons.append(cta)
            cta.setProperty("llBaseEnabled", self.accounts_service is not None)
            self.list_card.add_widget(cta)
            return

        active = self._active_index()
        default = self._default_index()

        for position, (index, account) in enumerate(accounts):
            if position:
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
        last_used = self._last_used_label(account.get("last_used"))
        # A Riot ID often already carries the shard ("Name#EUW"), and printing
        # it twice reads like a bug.
        if region and region.lower() in tagline.lower():
            region = ""
        detail_text = " - ".join(p for p in (tagline, region, last_used) if p)
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

        # Say up front when an account cannot possibly sign in - a password
        # that no longer decrypts (accounts.json copied from another machine,
        # or a different Windows user) is otherwise only discovered as a
        # mystery failure mid-switch.
        if not self._credentials_ok(index):
            warning = LLBadge("No password", Tone.WARNING, parent=row)
            warning.setToolTip(
                "No usable password is stored for this account. Use Edit to "
                "set one."
            )
            layout.addWidget(warning)

        # Account reordering affordance (§14)
        total_accounts = len(self._accounts())
        if total_accounts > 1:
            btn_up = LLButton(
                "▲", variant=ButtonVariant.GHOST, size=ButtonSize.SM, parent=row
            )
            btn_up.setToolTip("Move account up")
            btn_up.setEnabled(index > 0 and self.accounts_service is not None)
            btn_up.setProperty("llBaseEnabled", index > 0 and self.accounts_service is not None)
            btn_up.clicked.connect(lambda _c, i=index: self._on_move(i, -1))
            layout.addWidget(btn_up)

            btn_down = LLButton(
                "▼", variant=ButtonVariant.GHOST, size=ButtonSize.SM, parent=row
            )
            btn_down.setToolTip("Move account down")
            btn_down.setEnabled(index < total_accounts - 1 and self.accounts_service is not None)
            btn_down.setProperty("llBaseEnabled", index < total_accounts - 1 and self.accounts_service is not None)
            btn_down.clicked.connect(lambda _c, i=index: self._on_move(i, 1))
            layout.addWidget(btn_down)
            self._buttons.extend((btn_up, btn_down))

        btn_default = LLButton(
            "Set default", variant=ButtonVariant.GHOST, size=ButtonSize.SM, parent=row
        )
        btn_default.setEnabled(not is_default)
        btn_default.setProperty("llBaseEnabled", not is_default)
        btn_default.clicked.connect(lambda _c, i=index: self._on_set_default(i))
        layout.addWidget(btn_default)

        btn_edit = LLButton(
            "Edit", variant=ButtonVariant.GHOST, size=ButtonSize.SM, parent=row
        )
        btn_edit.setToolTip("Change this account's details or password")
        btn_edit.setEnabled(self.accounts_service is not None)
        btn_edit.setProperty("llBaseEnabled", self.accounts_service is not None)
        btn_edit.clicked.connect(lambda _c, i=index: self._on_edit(i))
        layout.addWidget(btn_edit)

        btn_remove = LLButton(
            "Remove", variant=ButtonVariant.GHOST, size=ButtonSize.SM, parent=row
        )
        btn_remove.setToolTip("Forget this account's saved credentials")
        btn_remove.setEnabled(self.accounts_service is not None)
        btn_remove.setProperty("llBaseEnabled", self.accounts_service is not None)
        btn_remove.clicked.connect(lambda _c, i=index: self._on_remove(i))
        layout.addWidget(btn_remove)

        btn_switch = LLButton(
            "Switch", variant=ButtonVariant.SECONDARY, size=ButtonSize.SM, parent=row
        )
        can_switch = not is_active and self.accounts_service is not None
        btn_switch.setEnabled(can_switch)
        btn_switch.setProperty("llBaseEnabled", can_switch)
        btn_switch.setToolTip(
            "This account is already signed in" if is_active
            else "Sign out and sign in as this account"
        )
        btn_switch.clicked.connect(lambda _c, i=index: self._on_switch(i))
        layout.addWidget(btn_switch)

        self._buttons.extend((btn_default, btn_edit, btn_remove, btn_switch))
        self._rows.append(row)
        return row

    # -------------------------------------------------------------- actions
    def _on_move(self, index: int, direction: int) -> None:
        if self.accounts_service is None or self._switching:
            return
        mover = getattr(self.accounts_service, "move_account", None)
        if callable(mover):
            try:
                mover(index, direction)
            except Exception:
                pass
        self.refresh()
    def _usernames(self, excluding: int = -1):
        return [
            (a.get("username") or "")
            for i, a in self._accounts()
            if i != excluding
        ]

    def _on_add(self) -> None:
        if self.accounts_service is None or self._switching:
            return
        dialog = AccountEditorModal(
            parent=self, existing_usernames=self._usernames()
        )
        if dialog.exec() != AccountEditorModal.Accepted:
            return

        values = dialog.values()
        adder = getattr(self.accounts_service, "add_account", None)
        if not callable(adder):
            return
        try:
            new_index = adder(
                values["label"], values["username"], values["password"] or "",
                values["tagline"], values["region"],
            )
        except Exception as exc:
            self.active_status.set_status(
                "Could not add that account", Tone.DANGER, str(exc)
            )
            return

        # The first account someone stores is the one they will be signing in
        # with, so make it the default rather than leaving the app with a list
        # and no default.
        if len(self._accounts()) == 1:
            setter = getattr(self.accounts_service, "set_default_account", None)
            if callable(setter):
                try:
                    setter(new_index)
                except Exception:
                    pass

        self.refresh()

    def _on_edit(self, index: int) -> None:
        if self.accounts_service is None or self._switching:
            return
        accounts = self._accounts()
        account = next((a for i, a in accounts if i == index), None)
        if account is None:
            return

        dialog = AccountEditorModal(
            account=account, parent=self,
            existing_usernames=self._usernames(excluding=index),
        )
        if dialog.exec() != AccountEditorModal.Accepted:
            return

        values = dialog.values()
        editor = getattr(self.accounts_service, "edit_account", None)
        if not callable(editor):
            return
        try:
            # password=None means "leave the stored one alone".
            editor(
                index,
                label=values["label"],
                username=values["username"],
                password=values["password"],
                tagline=values["tagline"],
                region=values["region"],
            )
        except Exception as exc:
            self.active_status.set_status(
                "Could not save those changes", Tone.DANGER, str(exc)
            )
            return
        self.refresh()

    def _on_remove(self, index: int) -> None:
        """
        Forget an account, after saying plainly what that means.

        Removing the account you are currently signed in as does not sign you
        out - the Riot Client keeps its own session - so the confirmation says
        so rather than letting you assume otherwise (§40).
        """
        if self.accounts_service is None or self._switching:
            return
        accounts = self._accounts()
        account = next((a for i, a in accounts if i == index), None)
        if account is None:
            return

        label = account.get("label") or account.get("username") or "this account"
        is_active = index == self._active_index()
        message = (
            "LeagueLoop will forget the saved credentials for {}. "
            "The Riot account itself is untouched, and you can add it again "
            "later by entering the password.".format(label)
        )
        if is_active:
            message += (
                "\n\nYou are signed in as this account right now. Removing it "
                "does not sign you out."
            )

        dialog = LLConfirmModal(
            "Remove {}?".format(label), message, "Remove account", parent=self
        )
        if dialog.exec() != LLConfirmModal.Accepted:
            return

        was_default = index == self._default_index()
        remover = getattr(self.accounts_service, "delete_account", None)
        if callable(remover):
            try:
                remover(index)
            except Exception as exc:
                self.active_status.set_status(
                    "Could not remove that account", Tone.DANGER, str(exc)
                )
                return

        # Deleting the default would otherwise leave the app with accounts but
        # no default, and nothing in the UI would say why.
        if was_default:
            remaining = self._accounts()
            setter = getattr(self.accounts_service, "set_default_account", None)
            if remaining and callable(setter):
                try:
                    setter(remaining[0][0])
                except Exception:
                    pass

        self.refresh()

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
