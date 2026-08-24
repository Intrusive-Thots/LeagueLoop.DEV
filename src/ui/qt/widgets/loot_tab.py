"""
Loot (UI/UX Master Plan §6, §15, §54, §55).

Opening loot is destructive and irreversible, so this screen follows the
plan's action-preview pattern (§15): it shows exactly what *would* be opened
first, and only then offers to do it. Nothing opens without an explicit
click, and the summary is refreshed from the client rather than cached.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStackedWidget,
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
from ui.qt.services.background import run_in_background
from utils.logger import Logger


class QtLootTab(QWidget):
    """Preview and open champion capsules, chests and other loot."""

    open_requested = Signal()

    def __init__(
        self,
        container=None,
        view_model=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.container = container
        self.view_model = view_model
        self.loot = self._resolve_loot_service(container)

        self._rows: List[Dict[str, Any]] = []
        #: False until the loot service has actually been asked. Distinguishes
        #: "you have no loot" from "we have not looked".
        self._has_read = False
        self._setup_ui()
        self._render_rows([])

        if view_model is not None:
            view_model.connection_changed.connect(self._on_connection_changed)
            self._on_connection_changed(view_model.state.client.connected)

    @staticmethod
    def _resolve_loot_service(container):
        """
        Use the container's loot service if it has one, else build our own.

        Constructing it here avoids adding a service to ApplicationContainer
        that only this screen uses; LootService is a thin wrapper over the
        LCU client and holds no state worth sharing.
        """
        if container is None:
            return None
        existing = getattr(container, "loot", None)
        if existing is not None:
            return existing

        lcu = getattr(container, "lcu", None)
        if lcu is None:
            return None
        try:
            from services.loot_service import LootService  # type: ignore

            return LootService(lcu)
        except Exception:
            return None

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        title = QLabel("Loot", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        root.addWidget(title)

        # --- status + actions ---------------------------------------------
        action_card = LLCard(parent=self)
        action_row = QHBoxLayout()
        action_row.setSpacing(SPACE_MD)

        self.status = LLStatus(
            "Not connected", Tone.NEUTRAL,
            "Connect the League Client to see your loot",
            parent=action_card,
        )
        action_row.addWidget(self.status)
        action_row.addStretch(1)

        self.btn_refresh = LLButton(
            "Refresh", variant=ButtonVariant.SECONDARY, parent=action_card
        )
        self.btn_refresh.clicked.connect(self.refresh)
        action_row.addWidget(self.btn_refresh)

        self.btn_open = LLButton(
            "Open all", variant=ButtonVariant.PRIMARY, parent=action_card
        )
        self.btn_open.setEnabled(False)
        self.btn_open.setToolTip(
            "Opening loot cannot be undone.\n"
            "Key fragments are forged into keys first."
        )
        self.btn_open.clicked.connect(self._on_open_all)
        action_row.addWidget(self.btn_open)

        action_card.add_layout(action_row)
        root.addWidget(action_card)

        # --- preview list ---------------------------------------------------
        self.stack = QStackedWidget(self)

        empty_holder = QWidget()
        empty_layout = QVBoxLayout(empty_holder)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        self.empty_card = LLCard(parent=empty_holder)
        # "Nothing to open" is a claim about your loot. Until we have actually
        # looked, the honest text is that we have not looked (§54).
        self.empty_label = QLabel("Loot has not been read yet.", self.empty_card)
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.empty_card.add_widget(self.empty_label)
        empty_layout.addWidget(self.empty_card)
        empty_layout.addStretch(1)
        self.stack.addWidget(empty_holder)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setSpacing(SPACE_MD)
        self.list_card = LLCard(title="Will be opened", parent=holder)
        # Key forging happens first and is irreversible, and fragments are
        # excluded from the list below — so it gets said here explicitly.
        self.forge_note = QLabel("", self.list_card)
        self.forge_note.setWordWrap(True)
        self.forge_note.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_SECONDARY) + " background: transparent;"
        )
        self.forge_note.setVisible(False)
        self.list_card.add_widget(self.forge_note)
        holder_layout.addWidget(self.list_card)
        holder_layout.addStretch(1)
        scroll.setWidget(holder)
        self.stack.addWidget(scroll)

        root.addWidget(self.stack, 1)

    # -------------------------------------------------------------- render
    def _on_connection_changed(self, connected: bool) -> None:
        self.btn_refresh.setEnabled(bool(connected) and self.loot is not None)
        if not connected:
            self.status.set_status(
                "Not connected", Tone.NEUTRAL,
                "Connect the League Client to see your loot",
            )
            self.btn_open.setEnabled(False)
            self._render_rows([])
        elif self.loot is None:
            self.status.set_status(
                "Loot service unavailable", Tone.WARNING,
                "This build has no loot service wired up",
            )
        else:
            # Asking the user to press Refresh on a connected client is asking
            # them to do the app's job. It also contradicted the panel below,
            # which said "Nothing to open" before anything had been read.
            self.status.set_status("Connected", Tone.SUCCESS, "Reading your loot…")
            self.refresh()

    def refresh(self) -> None:
        """Ask the loot service what is openable right now.

        Off the GUI thread: `summarize_openable` is `fetch_loot` plus one
        recipes GET per openable stack, and it is called from the
        connection-changed signal — so simply connecting to League froze the
        window for the duration.
        """
        if self.loot is None:
            self._render_rows([])
            return
        self._has_read = True
        self.btn_refresh.setEnabled(False)
        self.status.set_status("Reading your loot…", Tone.NEUTRAL, "")
        self._refresh_task = run_in_background(
            lambda: self.loot.summarize_openable() or [],
            on_done=self._on_rows_read,
            on_error=self._on_read_failed,
            owner=self,
            label="loot.summarize_openable",
        )

    def _on_read_failed(self, exc: Exception) -> None:
        self.btn_refresh.setEnabled(True)
        self.status.set_status("Could not read loot", Tone.DANGER, str(exc))
        self._render_rows([])

    def _on_rows_read(self, rows) -> None:
        self.btn_refresh.setEnabled(True)
        self._apply_rows(rows or [])

    def _apply_rows(self, rows) -> None:
        self._rows = rows
        self._sync_forge_note()
        openable = [r for r in rows if r.get("can_open")]
        total = sum(int(r.get("will_open") or 0) for r in openable)

        if total:
            self.status.set_status(
                "{} item{} ready".format(total, "" if total == 1 else "s"),
                Tone.SUCCESS,
                "Review below, then open",
            )
        else:
            self.status.set_status(
                "Nothing to open", Tone.NEUTRAL,
                "You have no chests, capsules or orbs ready.",
            )

        self.btn_open.setEnabled(bool(total))
        self._render_rows(rows)

    def _render_rows(self, rows: List[Dict[str, Any]]) -> None:
        layout = self.list_card.body
        while layout.count() > 1:
            item = layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        shown = [r for r in rows if r.get("can_open") or r.get("count")]
        if not shown:
            if self.loot is None:
                text = "Loot is not available in this build yet."
            elif not self._has_read:
                # Three different states that used to share one sentence.
                text = "Loot has not been read yet."
            else:
                text = "Nothing to open — your loot has no openable items."
            self.empty_label.setText(text)
            self.stack.setCurrentIndex(0)
            return

        self.stack.setCurrentIndex(1)
        for index, row in enumerate(shown):
            if index:
                self.list_card.add_widget(LLSeparator(parent=self.list_card))
            self.list_card.add_widget(self._loot_row(row))

    def _loot_row(self, row: Dict[str, Any]) -> QWidget:
        widget = QWidget(self.list_card)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(SPACE_SM)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        name = QLabel(str(row.get("name") or "Unknown"), widget)
        name.setStyleSheet(TEXT_BODY_STRONG.qss(color=TEXT_PRIMARY))
        text_col.addWidget(name)

        recipe = str(row.get("recipe_desc") or row.get("recipe") or "")
        if recipe:
            detail = QLabel(recipe, widget)
            detail.setWordWrap(True)
            detail.setStyleSheet(
                TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
            )
            text_col.addWidget(detail)

        layout.addLayout(text_col, 1)

        if row.get("needs_key"):
            layout.addWidget(LLBadge("Needs key", Tone.WARNING, parent=widget))

        will_open = int(row.get("will_open") or 0)
        if will_open:
            layout.addWidget(LLBadge("Opens {}".format(will_open), Tone.SUCCESS, parent=widget))

        count = QLabel("x{}".format(row.get("count", 0)), widget)
        count.setStyleSheet(TEXT_BODY.qss(color=TEXT_SECONDARY))
        layout.addWidget(count)

        return widget

    # -------------------------------------------------------------- actions
    def _on_open_all(self) -> None:
        """Irreversible - only ever runs from an explicit click (§40)."""
        self.open_requested.emit()
        opener = getattr(self.loot, "open_all", None)
        if not callable(opener):
            return
        self.btn_open.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.status.set_status("Opening…", Tone.NEUTRAL, "Talking to the client.")

        # The whole multi-pass open — key forging, up to four passes, a GET
        # per stack per pass, N craft POSTs and the sleeps between them —
        # used to run here, on the GUI thread. The window was unpaintable
        # throughout, so this very status line never rendered.
        self._open_task = run_in_background(
            opener,
            on_done=self._on_open_finished,
            on_error=self._on_open_failed,
            owner=self,
            label="loot.open_all",
        )

    def _on_open_failed(self, exc: Exception) -> None:
        Logger.error("LootTab", "Opening loot failed.", exc=exc)
        self.status.set_status("Could not open loot", Tone.DANGER, str(exc))
        self.refresh()

    def _on_open_finished(self, result) -> None:
        self._report_open(result)
        self.refresh()

    def _sync_forge_note(self) -> None:
        counter = getattr(self.loot, "count_key_fragments", None)
        fragments = 0
        if callable(counter):
            try:
                fragments = int(counter() or 0)
            except Exception as exc:
                Logger.debug("LootTab", "Could not count key fragments", exc=exc)
        if fragments:
            self.forge_note.setText(
                "{} key fragment{} will be forged into keys first. "
                "That cannot be undone either.".format(
                    fragments, "" if fragments == 1 else "s"
                )
            )
        self.forge_note.setVisible(bool(fragments))

    def _report_open(self, result) -> None:
        """Say what actually happened.

        The `OpenResult` used to be discarded and the screen reported "Loot
        opened" with a success tone even when nothing opened and every craft
        returned HTTP 500 — `open_all` is written never to raise, so the only
        path to a failure message was unreachable.
        """
        opened = int(getattr(result, "opened", 0) or 0)
        failed = int(getattr(result, "failed", 0) or 0)
        skipped = int(getattr(result, "skipped", 0) or 0)
        keys = int(getattr(result, "keys_crafted", 0) or 0)

        parts = []
        if keys:
            parts.append("{} key{} forged".format(keys, "" if keys == 1 else "s"))
        if opened:
            parts.append("{} opened".format(opened))
        if failed:
            parts.append("{} failed".format(failed))
        if skipped:
            parts.append("{} skipped".format(skipped))
        detail = ", ".join(parts) or "Nothing was openable."

        if result is None:
            self.status.set_status("Nothing was returned", Tone.WARNING, detail)
        elif opened == 0 and failed:
            self.status.set_status("Nothing opened", Tone.DANGER, detail)
        elif failed:
            self.status.set_status("Partly opened", Tone.WARNING, detail)
        elif opened or keys:
            self.status.set_status("Loot opened", Tone.SUCCESS, detail)
        else:
            self.status.set_status("Nothing to open", Tone.NEUTRAL, detail)

        Logger.info("LootTab", f"Open finished: {detail}",
                    opened=opened, failed=failed, skipped=skipped,
                    keys_crafted=keys)
