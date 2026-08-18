"""
LLActivityFeed — human-readable activity (UI/UX Master Plan §18).

The plan is specific about the difference:

    bad   [LCU] POST /lol-champ-select/v1/session/action
    good  Selected Jinx

So entries are product sentences, not protocol traces. Raw LCU detail belongs
in Diagnostics / Developer Mode (§58), and the feed defaults to IMPORTANT
rather than showing everything.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.button import LLButton  # noqa: F401  (kept for parity)
from ui.qt.components.status import Tone, tone_color, tone_glyph
from ui.qt.theme.colors import (
    BORDER_ACCENT,
    SURFACE_PANEL,
    SURFACE_PANEL_HOVER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.radii import RADIUS_SM
from ui.qt.theme.spacing import CONTROL_HEIGHT_SM, SPACE_MD, SPACE_SM, SPACE_XS
from ui.qt.theme.typography import FONT_FAMILY, TEXT_BODY, TEXT_CAPTION, WEIGHT_MEDIUM

MAX_ENTRIES = 200


class ActivityKind(Enum):
    """What kind of thing happened, mapped onto the shared status tones."""

    SUCCESS = Tone.SUCCESS
    INFO = Tone.INFO
    WARNING = Tone.WARNING
    ERROR = Tone.DANGER
    NEUTRAL = Tone.NEUTRAL


#: Which categories each filter shows. IMPORTANT is the default view (§18).
FILTERS = [
    ("IMPORTANT", "Important"),
    ("ALL", "All"),
    ("AUTOMATION", "Automation"),
    ("ERRORS", "Errors"),
]


@dataclass
class ActivityEntry:
    """One line in the feed."""

    text: str
    kind: ActivityKind = ActivityKind.NEUTRAL
    category: str = "AUTOMATION"
    important: bool = False
    timestamp: float = field(default_factory=time.time)

    def clock(self) -> str:
        return time.strftime("%H:%M", time.localtime(self.timestamp))


class LLActivityRow(QWidget):
    """A single activity line: glyph, text, time."""

    def __init__(self, entry: ActivityEntry, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, SPACE_XS // 2, 0, SPACE_XS // 2)
        layout.setSpacing(SPACE_SM)

        tone = entry.kind.value
        glyph = QLabel(tone_glyph(tone), self)
        glyph.setFixedWidth(12)
        glyph.setAlignment(Qt.AlignCenter)
        glyph.setStyleSheet(
            TEXT_BODY.qss(color=tone_color(tone)) + " background: transparent;"
        )
        layout.addWidget(glyph)

        text = QLabel(entry.text, self)
        text.setWordWrap(True)
        text.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_PRIMARY) + " background: transparent;"
        )
        layout.addWidget(text, 1)

        clock = QLabel(entry.clock(), self)
        clock.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        layout.addWidget(clock)

        self.setToolTip("{}  {}".format(entry.clock(), entry.text))


class LLActivityFeed(QWidget):
    """Filterable, capped list of recent activity."""

    def __init__(
        self,
        show_filters: bool = True,
        max_entries: int = MAX_ENTRIES,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._entries: List[ActivityEntry] = []
        self._filter = "IMPORTANT"
        self._max = max_entries

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACE_SM)

        self._buttons = {}
        if show_filters:
            row = QHBoxLayout()
            row.setSpacing(SPACE_SM)
            for key, label in FILTERS:
                btn = QPushButton(label, self)
                btn.setCheckable(True)
                btn.setChecked(key == self._filter)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setFixedHeight(CONTROL_HEIGHT_SM)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {TEXT_SECONDARY};
                        border: 1px solid transparent;
                        border-radius: {RADIUS_SM}px;
                        padding: 0px {SPACE_MD}px;
                        font-family: {FONT_FAMILY};
                        font-size: 12px;
                        font-weight: {WEIGHT_MEDIUM};
                    }}
                    QPushButton:hover {{
                        background-color: {SURFACE_PANEL_HOVER};
                        color: {TEXT_PRIMARY};
                    }}
                    QPushButton:checked {{
                        background-color: {SURFACE_PANEL};
                        color: {TEXT_PRIMARY};
                        border: 1px solid {BORDER_ACCENT};
                    }}
                """)
                btn.clicked.connect(lambda _c, k=key: self.set_filter(k))
                self._buttons[key] = btn
                row.addWidget(btn)
            row.addStretch(1)
            root.addLayout(row)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._holder = QWidget()
        self._holder.setStyleSheet("background: transparent;")
        self._list = QVBoxLayout(self._holder)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(0)
        self._list.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._holder)
        root.addWidget(self._scroll, 1)

        # Empty state (§54)
        self._empty = QLabel("Nothing yet. Activity will appear here.", self)
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        root.addWidget(self._empty)
        self._empty.setVisible(True)
        self._scroll.setVisible(False)

    # ---------------------------------------------------------------- API
    def add(self, entry: ActivityEntry) -> None:
        """Append an entry, newest first, capped."""
        self._entries.insert(0, entry)
        del self._entries[self._max:]
        self._rebuild()

    def log(self, text: str, kind: ActivityKind = ActivityKind.NEUTRAL,
            category: str = "AUTOMATION", important: bool = False) -> None:
        self.add(ActivityEntry(text=text, kind=kind, category=category,
                               important=important))

    def entries(self) -> List[ActivityEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()
        self._rebuild()

    def set_filter(self, key: str) -> None:
        self._filter = key
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)
        self._rebuild()

    def visible_entries(self) -> List[ActivityEntry]:
        if self._filter == "ALL":
            return list(self._entries)
        if self._filter == "IMPORTANT":
            return [e for e in self._entries
                    if e.important or e.kind in (ActivityKind.ERROR, ActivityKind.WARNING)]
        if self._filter == "ERRORS":
            return [e for e in self._entries if e.kind is ActivityKind.ERROR]
        return [e for e in self._entries if e.category == self._filter]

    # ------------------------------------------------------------ internals
    def _rebuild(self) -> None:
        while self._list.count():
            item = self._list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        visible = self.visible_entries()
        for entry in visible:
            self._list.addWidget(LLActivityRow(entry, self._holder))

        self._empty.setVisible(not visible)
        self._scroll.setVisible(bool(visible))
