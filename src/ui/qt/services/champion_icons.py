"""
Champion icon provider (UI/UX Master Plan §67, §68).

Champion art is loaded off the GUI thread and cached in memory, so scrolling
the grid back and forth never re-reads from disk and never blocks the UI
(§68: immediate visual update, asynchronous work, then state update).

Lookup order for a champion key (e.g. "Ahri", "LeeSin"):

    1. bundled repo assets   assets/champion_<Key>.png
    2. DDragon disk cache    <data dir>/cache/champion_<Key>.png
    3. no file -> caller falls back to an initials placeholder

Both locations use the same ``champion_<Key>.png`` naming that
``services.asset_manager`` already writes, so this shares the existing cache
rather than creating a second one.

Threading note: QImage may be created on a worker thread, QPixmap may not.
Workers therefore decode to QImage and the conversion happens in a slot on
the GUI thread.
"""
from __future__ import annotations

import os
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import QFont, QImage, QPainter, QPixmap

from ui.qt.theme.colors import (
    BORDER_DEFAULT,
    GOLD_PRIMARY,
    SURFACE_SUNKEN,
)
from ui.qt.theme.radii import RADIUS_SM
from ui.qt.theme.typography import FONT_FAMILY_PRIMARY, WEIGHT_BOLD

#: Cap the in-memory pixmap cache. Roughly 170 champions x a couple of sizes.
DEFAULT_CACHE_SIZE = 400


def _candidate_dirs(asset_manager=None) -> List[str]:
    """Directories to search for champion art, most-specific first."""
    dirs: List[str] = []

    for attr in ("cache_dir", "CACHE_DIR"):
        value = getattr(asset_manager, attr, None)
        if isinstance(value, str) and value:
            dirs.append(value)

    try:
        from utils.path_utils import get_data_dir  # type: ignore

        dirs.append(os.path.join(get_data_dir(), "cache"))
    except Exception:
        pass

    try:
        from utils.path_utils import get_asset_path  # type: ignore

        dirs.append(get_asset_path("assets"))
    except Exception:
        pass

    # Repo-relative fallback for `python run_qt.py` from a source checkout.
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    dirs.append(os.path.join(repo_root, "assets"))

    seen = set()
    unique = []
    for d in dirs:
        if d and d not in seen and os.path.isdir(d):
            seen.add(d)
            unique.append(d)
    return unique


class _LoadSignals(QObject):
    finished = Signal(str, int, object)  # key, size, QImage|None


class _IconLoadTask(QRunnable):
    """Decode one champion image off the GUI thread."""

    def __init__(self, key: str, size: int, paths: List[str], signals: _LoadSignals):
        super().__init__()
        self.key = key
        self.size = size
        self.paths = paths
        self.signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        image = None
        for path in self.paths:
            if not os.path.exists(path):
                continue
            candidate = QImage(path)
            if not candidate.isNull():
                image = candidate.scaled(
                    self.size,
                    self.size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                break
        self.signals.finished.emit(self.key, self.size, image)


class ChampionIconProvider(QObject):
    """
    Async, memory-cached champion art.

    Call :meth:`pixmap`. If the art is already cached you get it immediately;
    otherwise you get ``None``, a background load starts, and
    :attr:`icon_ready` fires when it is available.
    """

    icon_ready = Signal(str, int)  # champ key, size

    def __init__(
        self,
        asset_manager=None,
        cache_size: int = DEFAULT_CACHE_SIZE,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._dirs = _candidate_dirs(asset_manager)
        self._cache: "OrderedDict[Tuple[str, int], Optional[QPixmap]]" = OrderedDict()
        self._cache_size = cache_size
        self._pending: set = set()
        self._pool = QThreadPool.globalInstance()

        self._signals = _LoadSignals()
        self._signals.finished.connect(self._on_loaded)

    # ---------------------------------------------------------------- API
    def search_dirs(self) -> List[str]:
        return list(self._dirs)

    def pixmap(self, champ_key: str, size: int) -> Optional[QPixmap]:
        """
        Cached pixmap for a champion, or None while it loads.

        A cached ``None`` means "we looked and there is no art" — the caller
        should render a placeholder and we will not retry.
        """
        if not champ_key:
            return None

        entry = (champ_key, size)
        if entry in self._cache:
            self._cache.move_to_end(entry)
            return self._cache[entry]

        if entry not in self._pending:
            self._pending.add(entry)
            paths = [
                os.path.join(d, f"champion_{champ_key}.png") for d in self._dirs
            ]
            self._pool.start(_IconLoadTask(champ_key, size, paths, self._signals))

        return None

    def is_loading(self, champ_key: str, size: int) -> bool:
        return (champ_key, size) in self._pending

    def clear(self) -> None:
        self._cache.clear()

    def cache_info(self) -> Dict[str, int]:
        return {
            "cached": len(self._cache),
            "pending": len(self._pending),
            "capacity": self._cache_size,
        }

    # ------------------------------------------------------------ internals
    def _on_loaded(self, key: str, size: int, image) -> None:
        """Runs on the GUI thread: QImage -> QPixmap conversion is safe here."""
        entry = (key, size)
        self._pending.discard(entry)

        pixmap = None
        if isinstance(image, QImage) and not image.isNull():
            pixmap = QPixmap.fromImage(image)

        self._cache[entry] = pixmap
        self._cache.move_to_end(entry)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

        self.icon_ready.emit(key, size)


def initials_pixmap(name: str, size: int, device_ratio: float = 1.0) -> QPixmap:
    """
    Placeholder art: the champion's initials on a sunken tile.

    Used when no image file exists, so a tile always has something readable
    rather than an empty box (§53).
    """
    pixmap = QPixmap(int(size * device_ratio), int(size * device_ratio))
    pixmap.setDevicePixelRatio(device_ratio)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)

    rect = pixmap.rect().adjusted(0, 0, -1, -1)
    painter.setPen(Qt.NoPen)
    painter.setBrush(Qt.GlobalColor.transparent)

    from PySide6.QtGui import QColor, QPen

    painter.setBrush(QColor(SURFACE_SUNKEN))
    painter.setPen(QPen(QColor(BORDER_DEFAULT), 1))
    painter.drawRoundedRect(rect, RADIUS_SM, RADIUS_SM)

    letters = "".join(part[0] for part in name.split()[:2] if part).upper() or "?"
    if len(letters) == 1 and len(name) > 1:
        letters = name[:2].upper()

    font = painter.font()
    font.setFamily(FONT_FAMILY_PRIMARY)
    font.setPixelSize(max(10, int(size * 0.30)))
    font.setWeight(QFont.Weight(WEIGHT_BOLD))
    painter.setFont(font)
    painter.setPen(QColor(GOLD_PRIMARY))
    painter.drawText(rect, Qt.AlignCenter, letters)
    painter.end()

    return pixmap
