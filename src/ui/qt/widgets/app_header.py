"""
LLAppHeader — the persistent context band (UI/UX Master Plan §2.4, §3, §20).

A single fixed-height header that always answers "what is happening?" before
the user looks anywhere else:

    LEAGUELOOP        ◆ Champ Select | Ranked Solo | ● Automation on | ● Connected   — ✕

It carries the five things §2.4 requires to be permanently visible —
product, connection status, queue, current phase, automation status — plus
the window controls, and it owns window dragging so the drag affordance is
intentional rather than "anywhere in the window" (§27).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ui.qt.components.badge import LLBadge
from ui.qt.components.button import LLIconButton
from ui.qt.components.status import LLStatus, Tone
from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    GOLD_PRIMARY,
    SURFACE_APP_BACKGROUND,
)
from ui.qt.theme.spacing import (
    CONTROL_HEIGHT_SM,
    HEADER_HEIGHT,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
)
from ui.qt.theme.typography import TEXT_BRAND


class _VSeparator(QFrame):
    """Hairline divider between header groups (§39: separators over boxes)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedWidth(1)
        self.setFixedHeight(18)
        self.setStyleSheet(f"background-color: {BORDER_DEFAULT}; border: none;")


class LLAppHeader(QFrame):
    """
    Persistent application header.

    Connect a `ShellViewModel` with `bind(view_model)` and the header keeps
    itself current; nothing else needs to push updates into it.
    """

    minimize_requested = Signal()
    close_requested = Signal()
    orb_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("appHeader")
        self.setFixedHeight(HEADER_HEIGHT)
        self.setStyleSheet(f"""
            QFrame#appHeader {{
                background-color: {SURFACE_APP_BACKGROUND};
                border-bottom: 1px solid {BORDER_DEFAULT};
            }}
        """)

        self._drag_offset: Optional[QPoint] = None
        self._view_model = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_LG, 0, SPACE_SM, 0)
        layout.setSpacing(SPACE_MD)

        # --- Brand lockup -------------------------------------------------
        self.brand = QLabel("LeagueLoop", self)
        self.brand.setStyleSheet(
            TEXT_BRAND.qss(color=GOLD_PRIMARY) + " background: transparent;"
        )
        layout.addWidget(self.brand)

        layout.addStretch(1)

        # --- State cluster (§2.4) ----------------------------------------
        self.phase_status = LLStatus("Idle", Tone.NEUTRAL, compact=True, parent=self)
        layout.addWidget(self.phase_status)

        layout.addWidget(_VSeparator(self))

        self.queue_badge = LLBadge("No queue", Tone.NEUTRAL, parent=self)
        layout.addWidget(self.queue_badge)

        layout.addWidget(_VSeparator(self))

        self.automation_status = LLStatus(
            "Automation off", Tone.NEUTRAL, compact=True, parent=self
        )
        layout.addWidget(self.automation_status)

        layout.addWidget(_VSeparator(self))

        self.connection_status = LLStatus(
            "Disconnected", Tone.DANGER, compact=True, parent=self
        )
        layout.addWidget(self.connection_status)

        layout.addSpacing(SPACE_XS)

        # --- Window controls ---------------------------------------------
        self.btn_orb = LLIconButton(
            "◱", tooltip="Compact Orb Mode", size=CONTROL_HEIGHT_SM, parent=self
        )
        self.btn_orb.clicked.connect(self.orb_requested.emit)
        layout.addWidget(self.btn_orb)

        self.btn_minimize = LLIconButton(
            "─", tooltip="Minimize", size=CONTROL_HEIGHT_SM, parent=self
        )
        self.btn_minimize.clicked.connect(self.minimize_requested.emit)
        layout.addWidget(self.btn_minimize)

        self.btn_close = LLIconButton(
            "✕", tooltip="Close", size=CONTROL_HEIGHT_SM, danger_hover=True, parent=self
        )
        self.btn_close.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.btn_close)

    # -------------------------------------------------------------- binding
    def bind(self, view_model) -> None:
        """Subscribe to a ShellViewModel and render its current state."""
        self._view_model = view_model
        view_model.state_changed.connect(self._render)
        self._render()

    def _render(self, *_args) -> None:
        vm = self._view_model
        if vm is None:
            return

        text, tone, detail = vm.connection_status()
        self.connection_status.set_status(text, tone, detail)
        self.connection_status.setToolTip(f"{text} — {detail}" if detail else text)

        text, tone, detail = vm.phase_status()
        self.phase_status.set_status(text, tone, detail)
        self.phase_status.setToolTip(f"{text} — {detail}" if detail else text)

        text, tone, detail = vm.automation_status()
        self.automation_status.set_status(text, tone, detail)
        self.automation_status.setToolTip(f"{text} — {detail}" if detail else text)

        text, tone, detail = vm.queue_status()
        self.queue_badge.set_badge(text, tone)
        self.queue_badge.setToolTip(f"{text} — {detail}" if detail else text)

    # ------------------------------------------------------- window drag
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            window = self.window()
            self._drag_offset = (
                event.globalPosition().toPoint() - window.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)
