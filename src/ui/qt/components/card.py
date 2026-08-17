"""
LLCard / LLSection — grouping primitives (UI/UX Master Plan §38, §39).

§38: cards are for *meaningful* groups (Account, Automation, Recommended
Champion, Recent Activity). Wrapping every label in a card fragments the
interface, so LLSection exists for the lighter case: a titled group that
uses spacing and a section heading instead of a border.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    SURFACE_PANEL,
    TEXT_SECONDARY,
)
from ui.qt.theme.elevation import ELEVATION_FLAT, apply_elevation
from ui.qt.theme.radii import RADIUS_MD
from ui.qt.theme.spacing import SPACE_LG, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import TEXT_SECTION_TITLE


class LLCard(QFrame):
    """
    An elevated surface for a meaningful group of content.

    Use `card.body` (a QVBoxLayout) to add content, or `add_widget()`.
    """

    def __init__(
        self,
        title: Optional[str] = None,
        elevation: int = ELEVATION_FLAT,
        padding: int = SPACE_LG,
        spacing: int = SPACE_MD,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("llcard")
        self.setStyleSheet(f"""
            QFrame#llcard {{
                background-color: {SURFACE_PANEL};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD}px;
            }}
        """)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(padding, padding, padding, padding)
        self._layout.setSpacing(spacing)

        self._title_label: Optional[QLabel] = None
        if title:
            self._title_label = QLabel(title, self)
            self._title_label.setStyleSheet(
                TEXT_SECTION_TITLE.qss(color=TEXT_SECONDARY) + " background: transparent;"
            )
            self._layout.addWidget(self._title_label)

        if elevation != ELEVATION_FLAT:
            apply_elevation(self, elevation)

    @property
    def body(self) -> QVBoxLayout:
        """The card's content layout."""
        return self._layout

    def add_widget(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self._layout.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)

    def set_title(self, title: str) -> None:
        if self._title_label is not None:
            self._title_label.setText(title)


class LLSection(QWidget):
    """
    A titled group that relies on typography and spacing rather than a border.

    Preferred over LLCard when the grouping is light — §39 asks for a layered
    interface rather than a boxed one.
    """

    def __init__(
        self,
        title: Optional[str] = None,
        spacing: int = SPACE_SM,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(spacing)

        self._title_label: Optional[QLabel] = None
        if title:
            self._title_label = QLabel(title, self)
            self._title_label.setStyleSheet(
                TEXT_SECTION_TITLE.qss(color=TEXT_SECONDARY) + " background: transparent;"
            )
            self._layout.addWidget(self._title_label)

    @property
    def body(self) -> QVBoxLayout:
        return self._layout

    def add_widget(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self._layout.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)

    def set_title(self, title: str) -> None:
        if self._title_label is not None:
            self._title_label.setText(title)


class LLSeparator(QFrame):
    """A 1px subtle rule — used sparingly, per §39."""

    def __init__(self, horizontal: bool = True, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine if horizontal else QFrame.VLine)
        self.setFixedHeight(1) if horizontal else self.setFixedWidth(1)
        self.setStyleSheet(f"background-color: {BORDER_DEFAULT}; border: none;")
