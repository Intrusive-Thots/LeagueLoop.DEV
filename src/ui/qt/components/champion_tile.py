"""
LLChampionTile — the champion tile (UI/UX Master Plan §9, §65, §66).

The plan calls the champion grid a flagship component, and requires the full
state set rather than just "selected or not":

    default, hover, selected, priority, favorite,
    disabled, banned, unowned, loading, error

Those are modelled explicitly below. Per §62 no state is signalled by colour
alone — priority carries its rank number, favourite a star, banned a slash,
unowned a lock — so the grid stays readable in greyscale.

Standard sizes come from §65: SM 64x84, MD 80x104, LG 112x144.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QSizePolicy, QWidget

from ui.qt.components.focus import install_focus_visible
from ui.qt.theme.colors import (
    BORDER_ACTIVE,
    BORDER_DEFAULT,
    COLOR_DANGER,
    COLOR_WARNING,
    GOLD_PRIMARY,
    SURFACE_PANEL,
    SURFACE_PANEL_HOVER,
    SURFACE_SUNKEN,
    TEXT_DISABLED,
    TEXT_MUTED,
    TEXT_PRIMARY,
)
from ui.qt.theme.radii import RADIUS_MD
from ui.qt.theme.spacing import (
    CHAMPION_TILE_LG,
    CHAMPION_TILE_MD,
    CHAMPION_TILE_SM,
)
from ui.qt.theme.typography import FONT_FAMILY_PRIMARY, WEIGHT_BOLD, WEIGHT_MEDIUM


class TileSize(Enum):
    SM = "sm"
    MD = "md"
    LG = "lg"


_TILE_DIMS = {
    TileSize.SM: CHAMPION_TILE_SM,
    TileSize.MD: CHAMPION_TILE_MD,
    TileSize.LG: CHAMPION_TILE_LG,
}


@dataclass
class ChampionTileModel:
    """Everything the tile needs to render itself."""

    champ_id: int
    name: str
    key: str
    priority: Optional[int] = None   # 1-based rank, None if not prioritised
    favorite: bool = False
    owned: bool = True
    banned: bool = False
    disabled: bool = False           # e.g. already picked by a teammate
    error: bool = False              # art or data failed to load
    #: Community win rate, or None when nobody measured it. None must render
    #: as *nothing* — never as a placeholder percentage.
    winrate: Optional[float] = None
    #: Where the number came from, e.g. "lolalytics". Empty when unattributed.
    winrate_source: str = ""

    @property
    def selectable(self) -> bool:
        return not (self.banned or self.disabled)


class LLChampionTile(QFrame):
    """A single champion tile with the full §9 state set."""

    clicked = Signal(int, str)          # champ_id, name
    double_clicked = Signal(int, str)
    context_menu_requested = Signal(int, object)  # champ_id, global QPoint

    def __init__(
        self,
        model: ChampionTileModel,
        size: TileSize = TileSize.MD,
        icon_provider=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.model = model
        self.tile_size = size
        self._icon_provider = icon_provider
        self._selected = False
        self._hovered = False
        self._loading = True

        width, height = _TILE_DIMS[size]
        self.setFixedSize(width, height)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        install_focus_visible(self)

        self.setCursor(
            Qt.PointingHandCursor if model.selectable else Qt.ForbiddenCursor
        )
        self.setToolTip(self._tooltip_text())

    # ---------------------------------------------------------------- API
    @property
    def art_size(self) -> int:
        """Square edge of the art area."""
        return _TILE_DIMS[self.tile_size][0] - 12

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()

    def is_selected(self) -> bool:
        return self._selected

    def set_model(self, model: ChampionTileModel) -> None:
        self.model = model
        self.setCursor(
            Qt.PointingHandCursor if model.selectable else Qt.ForbiddenCursor
        )
        self.setToolTip(self._tooltip_text())
        self.update()

    def _tooltip_text(self) -> str:
        m = self.model
        bits = [m.name]
        if m.winrate is not None:
            # Attribution only when there is something to attribute. This
            # used to read "(Lolalytics)" on numbers from a hand-written table.
            source = getattr(m, "winrate_source", "") or ""
            bits.append(
                f"{m.winrate:.1f}% WR ({source})" if source
                else f"{m.winrate:.1f}% WR"
            )
        if m.priority:
            bits.append("Priority #{}".format(m.priority))
        if m.favorite:
            bits.append("Favourite")
        if m.banned:
            bits.append("Banned")
        if not m.owned:
            bits.append("Not owned")
        if m.disabled:
            bits.append("Unavailable")
        return "  -  ".join(bits)

    # ------------------------------------------------------------ painting
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        m = self.model
        rect = self.rect().adjusted(0, 0, -1, -1)

        # --- surface + border, ranked by state ---------------------------
        if m.disabled or m.banned:
            bg, border, border_w = SURFACE_SUNKEN, BORDER_DEFAULT, 1
        elif self._selected:
            bg, border, border_w = SURFACE_PANEL_HOVER, BORDER_ACTIVE, 2
        elif m.priority:
            bg, border, border_w = SURFACE_PANEL, GOLD_PRIMARY, 1
        elif self._hovered:
            bg, border, border_w = SURFACE_PANEL_HOVER, BORDER_ACTIVE, 1
        else:
            bg, border, border_w = SURFACE_PANEL, BORDER_DEFAULT, 1

        painter.setBrush(QColor(bg))
        painter.setPen(QPen(QColor(border), border_w))
        painter.drawRoundedRect(rect, RADIUS_MD, RADIUS_MD)

        # --- art ---------------------------------------------------------
        art = self.art_size
        art_rect = QRect(6, 6, art, art)
        pixmap = None
        if self._icon_provider is not None:
            pixmap = self._icon_provider.pixmap(m.key, art)
            self._loading = pixmap is None and self._icon_provider.is_loading(m.key, art)

        if pixmap is not None and not pixmap.isNull():
            painter.setOpacity(0.35 if (m.disabled or m.banned or not m.owned) else 1.0)
            painter.drawPixmap(art_rect, pixmap)
            painter.setOpacity(1.0)
        else:
            self._paint_art_fallback(painter, art_rect)

        # --- name --------------------------------------------------------
        name_color = TEXT_PRIMARY
        if m.disabled or m.banned:
            name_color = TEXT_DISABLED
        elif not m.owned:
            name_color = TEXT_MUTED

        font = painter.font()
        font.setFamily(FONT_FAMILY_PRIMARY)
        font.setPixelSize(10 if self.tile_size is TileSize.SM else 11)
        font.setWeight(QFont.Weight(WEIGHT_BOLD if m.priority else WEIGHT_MEDIUM))
        painter.setFont(font)
        painter.setPen(QColor(name_color))

        name_rect = QRect(3, art + 8, self.width() - 6, self.height() - art - 10)
        metrics = painter.fontMetrics()
        label = metrics.elidedText(m.name, Qt.ElideRight, name_rect.width())
        painter.drawText(name_rect, Qt.AlignHCenter | Qt.AlignTop, label)

        self._paint_badges(painter, art_rect)
        painter.end()

    def _paint_art_fallback(self, painter: QPainter, rect: QRect) -> None:
        """Loading shimmer (§53) or initials when there is no art."""
        painter.setBrush(QColor(SURFACE_SUNKEN))
        painter.setPen(QPen(QColor(BORDER_DEFAULT), 1))
        painter.drawRoundedRect(rect, 4, 4)

        if self._loading:
            # Skeleton bar rather than a spinner - preserves layout geometry.
            bar = QRect(
                rect.left() + 8,
                rect.center().y() - 3,
                rect.width() - 16,
                6,
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(BORDER_DEFAULT))
            painter.drawRoundedRect(bar, 3, 3)
            return

        letters = "".join(p[0] for p in self.model.name.split()[:2] if p).upper()
        if len(letters) < 2:
            letters = self.model.name[:2].upper()

        font = painter.font()
        font.setFamily(FONT_FAMILY_PRIMARY)
        font.setPixelSize(max(11, int(rect.width() * 0.30)))
        font.setWeight(QFont.Weight(WEIGHT_BOLD))
        painter.setFont(font)
        painter.setPen(QColor(TEXT_MUTED if self.model.error else GOLD_PRIMARY))
        painter.drawText(rect, Qt.AlignCenter, "!" if self.model.error else letters)

    def _paint_badges(self, painter: QPainter, art_rect: QRect) -> None:
        """Priority rank, favourite star, ban slash, unowned lock (§62)."""
        m = self.model

        if m.priority:
            size = 16
            badge = QRect(art_rect.right() - size + 2, art_rect.top() - 2, size, size)
            painter.setBrush(QColor(GOLD_PRIMARY))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(badge)

            font = painter.font()
            font.setPixelSize(9)
            font.setWeight(QFont.Weight(WEIGHT_BOLD))
            painter.setFont(font)
            painter.setPen(QColor("#010A13"))
            painter.drawText(badge, Qt.AlignCenter, str(m.priority))

        if m.favorite:
            # Drawn as a polygon rather than a glyph: star characters render
            # inconsistently (or not at all) depending on installed fonts.
            self._paint_star(
                painter,
                QRect(art_rect.left() - 3, art_rect.top() - 3, 16, 16),
            )

        if m.banned:
            painter.setPen(QPen(QColor(COLOR_DANGER), 2))
            painter.drawLine(
                art_rect.left() + 4, art_rect.bottom() - 4,
                art_rect.right() - 4, art_rect.top() + 4,
            )

        if not m.owned and not m.banned:
            font = painter.font()
            font.setPixelSize(10)
            font.setWeight(QFont.Weight(WEIGHT_BOLD))
            painter.setFont(font)
            painter.setPen(QColor(TEXT_MUTED))
            painter.drawText(
                QRect(art_rect.left(), art_rect.bottom() - 13, art_rect.width(), 12),
                Qt.AlignCenter,
                "LOCKED",
            )

        if m.winrate is not None and not m.banned and not m.favorite and self.tile_size is not TileSize.SM:
            font = painter.font()
            font.setPixelSize(9)
            font.setWeight(QFont.Weight(WEIGHT_BOLD))
            painter.setFont(font)
            wr_col = QColor("#0AC8B9") if m.winrate >= 50.0 else QColor(TEXT_MUTED)
            painter.setPen(wr_col)
            painter.drawText(
                QRect(art_rect.left() + 2, art_rect.top() + 2, art_rect.width() - 4, 12),
                Qt.AlignLeft | Qt.AlignTop,
                f"{m.winrate:.1f}%",
            )

    @staticmethod
    def _paint_star(painter: QPainter, box: QRect) -> None:
        """Five-pointed favourite marker on a dark disc for contrast."""
        import math

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(1, 10, 19, 210))
        painter.drawEllipse(box)

        cx, cy = box.center().x() + 0.5, box.center().y() + 0.5
        outer = box.width() * 0.36
        inner = outer * 0.45

        path = QPainterPath()
        for i in range(10):
            radius = outer if i % 2 == 0 else inner
            angle = math.radians(-90 + i * 36)
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()

        painter.setBrush(QColor(COLOR_WARNING))
        painter.drawPath(path)

    # ------------------------------------------------------------- events
    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.model.selectable:
            self.setFocus(Qt.MouseFocusReason)
            self.clicked.emit(self.model.champ_id, self.model.name)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.model.selectable:
            self.double_clicked.emit(self.model.champ_id, self.model.name)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        self.context_menu_requested.emit(self.model.champ_id, event.globalPos())
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if self.model.selectable:
                self.clicked.emit(self.model.champ_id, self.model.name)
                event.accept()
                return
        super().keyPressEvent(event)

    def on_icon_ready(self, key: str, size: int) -> None:
        """Repaint when this tile's art finishes loading."""
        if key == self.model.key and size == self.art_size:
            self._loading = False
            self.update()
