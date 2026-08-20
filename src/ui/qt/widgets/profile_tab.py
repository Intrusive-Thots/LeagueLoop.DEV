"""
Profile (UI/UX Master Plan §21, §22).

§22 is emphatic: the profile starts *empty* and fills in as real matches are
recorded. No placeholder rows, no invented averages — "Do not create
fake-looking placeholder data." So every number here comes from the local
match database, and when there is none the screen says so and names the next
useful action.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.badge import LLBadge
from ui.qt.components.card import LLCard, LLSeparator
from ui.qt.components.status import Tone
from ui.qt.theme.colors import (
    COLOR_DANGER,
    COLOR_SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.qt.theme.spacing import CONTENT_MARGIN, SPACE_LG, SPACE_MD, SPACE_SM
from ui.qt.theme.typography import (
    TEXT_BODY,
    TEXT_BODY_STRONG,
    TEXT_CAPTION,
    TEXT_DISPLAY,
    TEXT_PAGE_TITLE,
)

MAX_RECENT = 10
MAX_CHAMPIONS = 5


def _kda(match: Dict[str, Any]) -> str:
    return "{}/{}/{}".format(
        match.get("kills", 0), match.get("deaths", 0), match.get("assists", 0)
    )


def _duration(match: Dict[str, Any]) -> str:
    seconds = int(match.get("duration_s", 0) or 0)
    return "{}m {:02d}s".format(seconds // 60, seconds % 60)


class QtProfileTab(QWidget):
    """Match history and champion preferences, built only from real data."""

    def __init__(
        self,
        container=None,
        view_model=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.container = container
        self.db = getattr(container, "db", None) if container else None
        self.view_model = view_model

        self._setup_ui()
        self.refresh()

        if view_model is not None:
            view_model.state_changed.connect(self._render_identity)
            self._render_identity()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(CONTENT_MARGIN, SPACE_LG, CONTENT_MARGIN, SPACE_LG)
        root.setSpacing(SPACE_MD)

        title = QLabel("Profile", self)
        title.setStyleSheet(TEXT_PAGE_TITLE.qss(color=TEXT_SECONDARY))
        root.addWidget(title)

        # --- identity -----------------------------------------------------
        self.identity_card = LLCard(parent=self)
        identity_row = QHBoxLayout()
        identity_row.setSpacing(SPACE_MD)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        self.summoner_name = QLabel("Not signed in", self.identity_card)
        self.summoner_name.setStyleSheet(TEXT_DISPLAY.qss(color=TEXT_PRIMARY))
        name_col.addWidget(self.summoner_name)

        self.summoner_detail = QLabel("Connect the League Client to see your profile",
                                      self.identity_card)
        self.summoner_detail.setStyleSheet(
            TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        name_col.addWidget(self.summoner_detail)
        identity_row.addLayout(name_col)
        identity_row.addStretch(1)

        self.match_count_badge = LLBadge("0 matches", Tone.NEUTRAL, parent=self.identity_card)
        identity_row.addWidget(self.match_count_badge)

        self.identity_card.add_layout(identity_row)
        root.addWidget(self.identity_card)

        # --- empty vs populated -------------------------------------------
        self.stack = QStackedWidget(self)

        # 0: empty state (§22)
        empty_holder = QWidget()
        empty_layout = QVBoxLayout(empty_holder)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_card = LLCard(parent=empty_holder)
        empty_title = QLabel("No match data yet", empty_card)
        empty_title.setStyleSheet(TEXT_BODY_STRONG.qss(color=TEXT_PRIMARY))
        empty_card.add_widget(empty_title)
        empty_body = QLabel(
            "Play a match with LeagueLoop running and your champion profile "
            "will start building here.",
            empty_card,
        )
        empty_body.setWordWrap(True)
        empty_body.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        empty_card.add_widget(empty_body)
        empty_layout.addWidget(empty_card)
        empty_layout.addStretch(1)
        self.stack.addWidget(empty_holder)

        # 1: populated
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        data_holder = QWidget()
        data_holder.setStyleSheet("background: transparent;")
        self.data_layout = QVBoxLayout(data_holder)
        self.data_layout.setContentsMargins(0, 0, 0, 0)
        self.data_layout.setSpacing(SPACE_MD)

        self.champions_card = LLCard(title="Most played", parent=data_holder)
        self.data_layout.addWidget(self.champions_card)

        self.matches_card = LLCard(title="Recent matches", parent=data_holder)
        self.data_layout.addWidget(self.matches_card)

        self.data_layout.addStretch(1)
        scroll.setWidget(data_holder)
        self.stack.addWidget(scroll)

        root.addWidget(self.stack, 1)

    # -------------------------------------------------------------- render
    def _render_identity(self, *_args) -> None:
        if self.view_model is None:
            return
        client = self.view_model.state.client
        if client.summoner_name:
            self.summoner_name.setText(client.summoner_name)
            self.summoner_detail.setText("Connected")
        else:
            self.summoner_name.setText("Not signed in")
            self.summoner_detail.setText(
                "Connect the League Client to see your profile"
            )

    def _clear_card(self, card: LLCard) -> None:
        """Remove everything below the card's title."""
        layout = card.body
        while layout.count() > 1:
            item = layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def refresh(self) -> None:
        """Reload from the local match database."""
        matches: List[Dict[str, Any]] = []
        if self.db is not None:
            try:
                matches = self.db.get_recent_matches(limit=MAX_RECENT) or []
            except Exception:
                matches = []

        self.match_count_badge.set_badge(
            "{} match{}".format(len(matches), "" if len(matches) == 1 else "es"),
            Tone.ACCENT if matches else Tone.NEUTRAL,
        )

        if not matches:
            self.stack.setCurrentIndex(0)
            return

        self.stack.setCurrentIndex(1)
        self._render_champions(matches)
        self._render_matches(matches)

    def _render_champions(self, matches: List[Dict[str, Any]]) -> None:
        self._clear_card(self.champions_card)

        counts: Dict[str, int] = {}
        wins: Dict[str, int] = {}
        for match in matches:
            name = str(match.get("champion_name") or "Unknown")
            counts[name] = counts.get(name, 0) + 1
            if match.get("win"):
                wins[name] = wins.get(name, 0) + 1

        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        for index, (name, played) in enumerate(ranked[:MAX_CHAMPIONS]):
            if index:
                self.champions_card.add_widget(
                    LLSeparator(parent=self.champions_card)
                )
            row = QWidget(self.champions_card)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 2, 0, 2)
            row_layout.setSpacing(SPACE_SM)

            label = QLabel(name, row)
            label.setStyleSheet(TEXT_BODY_STRONG.qss(color=TEXT_PRIMARY))
            row_layout.addWidget(label)
            row_layout.addStretch(1)

            won = wins.get(name, 0)
            rate = QLabel("{}W {}L".format(won, played - won), row)
            rate.setStyleSheet(
                TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
            )
            row_layout.addWidget(rate)

            count = QLabel(str(played), row)
            count.setStyleSheet(TEXT_BODY.qss(color=TEXT_SECONDARY))
            row_layout.addWidget(count)

            self.champions_card.add_widget(row)

    def _render_matches(self, matches: List[Dict[str, Any]]) -> None:
        self._clear_card(self.matches_card)

        for index, match in enumerate(matches):
            if index:
                self.matches_card.add_widget(LLSeparator(parent=self.matches_card))

            row = QWidget(self.matches_card)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 2, 0, 2)
            row_layout.setSpacing(SPACE_SM)

            won = bool(match.get("win"))
            result = LLBadge(
                "WIN" if won else "LOSS",
                Tone.SUCCESS if won else Tone.DANGER,
                parent=row,
            )
            row_layout.addWidget(result)

            champ = QLabel(str(match.get("champion_name") or "Unknown"), row)
            champ.setStyleSheet(TEXT_BODY_STRONG.qss(color=TEXT_PRIMARY))
            row_layout.addWidget(champ)
            row_layout.addStretch(1)

            for text in (_kda(match), _duration(match)):
                label = QLabel(text, row)
                label.setStyleSheet(
                    TEXT_CAPTION.qss(color=TEXT_MUTED) + " background: transparent;"
                )
                row_layout.addWidget(label)

            self.matches_card.add_widget(row)
