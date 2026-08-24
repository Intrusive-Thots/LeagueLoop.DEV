"""
A layout that wraps onto the next line instead of overflowing.

`QHBoxLayout` has exactly one strategy when it runs out of room: squeeze its
children below their minimum size. That is what put four buttons — "Sort by
winrate", "Paste list", "Remove", "Clear all" — into 100 pixels of a narrow
panel, each rendering as a sliver with elided text, and it is what made the
champion grid's ten filter chips set a 500px floor on the whole window.

A flow layout instead does what a paragraph of text does: fill the line, then
start a new one. The row is as tall as it needs to be and no child is ever
smaller than it asked to be.

    row = LLFlowLayout(spacing=SPACE_SM)
    row.addWidget(btn_sort)
    row.addWidget(btn_paste)

`heightForWidth` is implemented, which is the part that makes it behave
inside a `QVBoxLayout`: the parent asks "how tall are you if I give you this
width", and the answer changes as the panel narrows.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QWidgetItem

#: Qt's own "no limit" sentinel (QWIDGETSIZE_MAX), not exported by PySide6.
_UNBOUNDED = (1 << 24) - 1


class LLFlowLayout(QLayout):
    """Left-to-right layout that wraps when the line is full."""

    def __init__(
        self,
        parent=None,
        margins: Optional[QMargins] = None,
        spacing: int = 8,
        v_spacing: Optional[int] = None,
    ) -> None:
        super().__init__(parent)
        self._items: List[QWidgetItem] = []
        self._h_spacing = spacing
        self._v_spacing = spacing if v_spacing is None else v_spacing
        self.setContentsMargins(margins or QMargins(0, 0, 0, 0))

    # -------------------------------------------------------- QLayout API
    def addItem(self, item) -> None:  # noqa: N802 (Qt override)
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        """The widest single item, not the sum of all of them.

        This is the whole point: a flow layout can always fit in the width of
        its largest child, because everything else wraps below it.
        """
        size = QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )

    def maximumSize(self) -> QSize:  # noqa: N802
        """Never absorb a layout's spare space.

        Without this a flow row is treated as infinitely stretchable, so when
        the widget below it is hidden — the champion grid's scroll area, in
        the empty state — the vertical layout hands the slack to the chip row
        and leaves a hundred pixels of nothing between the filters and the
        roles.
        """
        width = self.geometry().width() or _UNBOUNDED
        return QSize(_UNBOUNDED, self.heightForWidth(width))

    # ------------------------------------------------------------ internals
    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x, y = effective.x(), effective.y()
        line_height = 0

        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_spacing
            if next_x - self._h_spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + self._v_spacing
                next_x = x + hint.width() + self._h_spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()


__all__ = ["LLFlowLayout"]
