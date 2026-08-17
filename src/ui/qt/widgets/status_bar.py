"""
LLStatusBar — the fixed footer status line (UI/UX Master Plan §3, §57).

One quiet line that summarises the session without becoming a telemetry
dump. Target density from §57:

    Champ Select  •  Ranked Solo  •  Automation on

Raw LCU internals belong in Diagnostics / Developer Mode (§58), never here.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    SURFACE_APP_BACKGROUND,
    TEXT_MUTED,
    TEXT_SECONDARY,
)
from ui.qt.theme.spacing import FOOTER_HEIGHT, SPACE_LG, SPACE_SM
from ui.qt.theme.typography import TEXT_CAPTION


class LLStatusBar(QFrame):
    """Persistent one-line status footer."""

    def __init__(self, version: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(FOOTER_HEIGHT)
        self.setStyleSheet(f"""
            QFrame#statusBar {{
                background-color: {SURFACE_APP_BACKGROUND};
                border-top: 1px solid {BORDER_DEFAULT};
            }}
        """)

        self._view_model = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_LG, 0, SPACE_LG, 0)
        layout.setSpacing(SPACE_SM)
        layout.setAlignment(Qt.AlignVCenter)

        self.summary = QLabel("Starting…", self)
        self.summary.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_SECONDARY) + " background: transparent;"
        )
        layout.addWidget(self.summary)

        layout.addStretch(1)

        self.meta = QLabel(version, self)
        self.meta.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        layout.addWidget(self.meta)

    # -------------------------------------------------------------- binding
    def bind(self, view_model) -> None:
        """Subscribe to a ShellViewModel's footer summary."""
        self._view_model = view_model
        view_model.summary_changed.connect(self.set_summary)
        self.set_summary(view_model.footer_summary())

    def set_summary(self, text: str) -> None:
        self.summary.setText(text or "Ready")

    def set_meta(self, text: str) -> None:
        self.meta.setText(text)
