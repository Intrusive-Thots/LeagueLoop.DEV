"""
Keeps a Qt window glued to the League Client.

The geometry rules live in `companion_position`, which is pure and knows
nothing about Qt. This is the thin part that owns a widget: it takes
`ClientWindowState`, asks for a placement, and moves the window.

It also owns the follow-the-client behaviour that makes the panel feel
attached rather than merely nearby:

* client moves or resizes  -> the panel moves with it
* client minimises         -> the panel hides, and remembers that it was
                              only hidden because of the client
* client restores          -> the panel comes back where it belongs
* client closes            -> the panel is left alone, wherever it is, so
                              the user can still reach it

The "remembers why it was hidden" part matters. A panel that hides when the
client minimises must not stay hidden when the user explicitly opened it, and
must not re-appear over a client the user deliberately minimised.
"""
from __future__ import annotations

from typing import Optional

from core.state import ClientWindowState
from ui.qt.services.companion_position import (
    DEFAULT_GAP,
    SIDE_RIGHT,
    Placement,
    place_companion,
    qt_available_screens,
)
from utils.logger import Logger

TAG = "Companion"


class CompanionAnchor:
    """Positions one widget relative to the League Client window."""

    def __init__(
        self,
        widget,
        gap: int = DEFAULT_GAP,
        preferred_side: str = SIDE_RIGHT,
        enabled: bool = True,
    ) -> None:
        self._widget = widget
        self.gap = gap
        self.preferred_side = preferred_side
        self.enabled = enabled

        #: True when *we* hid the widget because the client minimised, as
        #: opposed to the user closing it.
        self._hidden_by_client = False
        self._last_placement: Optional[Placement] = None

    # ------------------------------------------------------------- placing
    def placement_for(self, window: ClientWindowState) -> Optional[Placement]:
        """Where the panel would go, or None if the client cannot anchor it."""
        if not window.usable:
            return None
        screens = qt_available_screens()
        if not screens:
            # Qt is not up, or reported nothing. Unknown is not the same as
            # "no screens" — refuse to place rather than guessing (0, 0).
            return None
        size = (self._widget.width(), self._widget.height())
        return place_companion(
            client_rect=window.rect,
            panel_size=size,
            screens=screens,
            gap=self.gap,
            preferred_side=self.preferred_side,
        )

    def apply(self, window: ClientWindowState) -> Optional[Placement]:
        """React to the client's window. Returns the placement used, if any."""
        if not self.enabled:
            return None

        # Client gone: leave the panel where it is. Hiding it here would take
        # away the user's way back into the app.
        if not window.found:
            self._release()
            return None

        if window.minimized:
            self._hide_with_client()
            return None

        placement = self.placement_for(window)
        if placement is None:
            return None

        self._restore_with_client()
        if (self._last_placement is None
                or (placement.x, placement.y) !=
                (self._last_placement.x, self._last_placement.y)):
            self._widget.move(placement.x, placement.y)
            if (self._last_placement is None
                    or placement.side != self._last_placement.side
                    or placement.overlapping != self._last_placement.overlapping):
                Logger.debug(
                    TAG, f"Panel placed {placement.reason}.",
                    x=placement.x, y=placement.y, side=placement.side,
                )
        self._last_placement = placement
        return placement

    # ------------------------------------------------------ visibility
    def _hide_with_client(self) -> None:
        if not self._widget.isVisible():
            return
        self._hidden_by_client = True
        try:
            self._widget.hide()
        except Exception as exc:
            Logger.debug(TAG, "Could not hide the panel", exc=exc)

    def _restore_with_client(self) -> None:
        if not self._hidden_by_client:
            return
        self._hidden_by_client = False
        try:
            self._widget.show()
        except Exception as exc:
            Logger.debug(TAG, "Could not restore the panel", exc=exc)

    def _release(self) -> None:
        """The client is gone. Stop treating the panel as attached."""
        self._hidden_by_client = False
        self._last_placement = None

    @property
    def hidden_by_client(self) -> bool:
        return self._hidden_by_client
