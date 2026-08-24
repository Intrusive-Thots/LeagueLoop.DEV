"""
The dodge blacklist editor.

The engine has always been able to leave a draft when a named player lands on
your team. It does that by force-closing the League Client, which costs you
the queue timer — and until now there was no screen anywhere that let you see
the list, add to it, or clear it. A value left in `config.json` would keep
killing the client with no way to find out why.

The list is stored as a comma-separated string under `dodge_blacklist`, which
is the shape the engine has always read. One name per line here, because
Riot IDs contain a `#` and commas are hard to see.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QWidget

from core.config_keys import DODGE_BLACKLIST, DODGE_BLACKLIST_ENABLED
from ui.qt.components.modal import LLModal
from ui.qt.components.status import LLStatus, Tone
from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    SURFACE_PANEL,
    TEXT_MUTED,
    TEXT_PRIMARY,
)
from ui.qt.theme.radii import RADIUS_MD
from ui.qt.theme.spacing import SPACE_SM
from ui.qt.theme.typography import TEXT_BODY, TEXT_MICRO
from utils.logger import Logger


def parse_blacklist(raw) -> List[str]:
    """The stored value as a list of names.

    Accepts the comma-separated string the engine reads and the list form an
    older config may hold, so neither shape is lost on a round trip.
    """
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        entries = list(raw)
    else:
        entries = str(raw).replace("\n", ",").split(",")
    seen, out = set(), []
    for entry in entries:
        name = str(entry).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def format_blacklist(names) -> str:
    """The list in the shape the engine reads."""
    return ", ".join(parse_blacklist(names))


class QtBlacklistDialog(LLModal):
    """Edit the list of players whose games you want to leave."""

    def __init__(self, config=None, parent: Optional[QWidget] = None):
        super().__init__(
            "Dodge blacklist", parent=parent, confirm_text="Save",
        )
        self.config = config

        warning = LLStatus(
            "This closes the League Client",
            Tone.WARNING,
            "Leaving a draft this way costs you the queue timer, and any "
            "champion you had already locked.",
            parent=self,
        )
        self.add_widget(warning)

        caption = QLabel(
            "One player per line. A summoner name on its own matches any "
            "tag; add the tag to match exactly.",
            self,
        )
        caption.setWordWrap(True)
        caption.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.add_widget(caption)

        self.editor = QPlainTextEdit(self)
        self.editor.setPlaceholderText("Someone\nSomebodyElse#EUW")
        self.editor.setMinimumHeight(180)
        self.editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {SURFACE_PANEL};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD}px;
                padding: {SPACE_SM}px;
                color: {TEXT_PRIMARY};
            }}
        """)
        self.add_widget(self.editor)

        self.count_label = QLabel("", self)
        self.count_label.setStyleSheet(
            TEXT_MICRO.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.add_widget(self.count_label)
        self.editor.textChanged.connect(self._sync_count)

        self._load()
        self._sync_count()

    # ------------------------------------------------------------- state
    def _load(self) -> None:
        if not self.config:
            return
        names = parse_blacklist(self.config.get(DODGE_BLACKLIST, ""))
        self.editor.setPlainText("\n".join(names))

    def names(self) -> List[str]:
        return parse_blacklist(self.editor.toPlainText())

    def _sync_count(self) -> None:
        count = len(self.names())
        if not count:
            self.count_label.setText(
                "Empty — nothing will be dodged, whatever the switch says."
            )
            return
        enabled = bool(self.config.get(DODGE_BLACKLIST_ENABLED, False)) \
            if self.config else False
        self.count_label.setText(
            "{} player{} listed. Dodging is currently {}.".format(
                count, "" if count == 1 else "s",
                "on" if enabled else "off",
            )
        )

    def accept(self) -> None:  # noqa: D102 (QDialog override)
        if self.config:
            names = self.names()
            self.config.set(DODGE_BLACKLIST, format_blacklist(names))
            Logger.info(
                "Blacklist", f"Dodge blacklist saved with {len(names)} entries.",
                count=len(names),
            )
        super().accept()
