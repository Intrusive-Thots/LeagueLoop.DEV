"""
FeatherEdge: A vertical gradient blending strip that feathers the companion window
seamlessly into the adjacent League Client.
"""
from dataclasses import dataclass
import sys
import tkinter as tk
from typing import Optional, Tuple
from ui.components.color_utils import interpolate_color

# Default feather gradient bounds
DEFAULT_CLIENT_EDGE_COLOR = "#010A13"   # League Client dark edge tone
DEFAULT_APP_BG_COLOR = "#091428"        # LeagueLoop primary background tone
DEFAULT_GOLD_SEAM = "#785A28"           # Hextech antique gold accent tone


@dataclass
class FeatherEdgeConfig:
    """Configuration options for FeatherEdge styling and dimensions."""
    width: int = 24
    side: str = "left"
    client_color: str = DEFAULT_CLIENT_EDGE_COLOR
    app_color: str = DEFAULT_APP_BG_COLOR
    seam_color: str = DEFAULT_GOLD_SEAM


class FeatherEdge(tk.Canvas):
    """A vertical gradient canvas placed on the docking seam of the companion.
    
    Generates a smooth horizontal color transition from the client's outer edge color
    into the companion window's background, with an ultra-thin Hextech gold seam line.
    """

    def __init__(
        self,
        master,
        config: Optional[FeatherEdgeConfig] = None,
        **kwargs
    ):
        cfg = config or FeatherEdgeConfig()
        width = kwargs.pop("width", cfg.width)
        side = kwargs.pop("side", cfg.side)
        client_color = kwargs.pop("client_color", cfg.client_color)
        app_color = kwargs.pop("app_color", cfg.app_color)
        seam_color = kwargs.pop("seam_color", cfg.seam_color)

        super().__init__(
            master,
            width=width,
            bg=app_color,
            highlightthickness=0,
            bd=0,
            **kwargs
        )
        self.feather_width = width
        self.side = side  # 'left' (docked to client's right side) or 'right' (docked to client's left side)
        self.client_color = client_color
        self.app_color = app_color
        self.seam_color = seam_color
        self._current_h = 0

        self.bind("<Configure>", self._on_resize)

    def update_colors(
        self,
        client_color: Optional[str] = None,
        app_color: Optional[str] = None,
        seam_color: Optional[str] = None,
    ) -> None:
        """Update gradient stop colors and re-render."""
        changed = False
        if client_color and client_color != self.client_color:
            self.client_color = client_color
            changed = True
        if app_color and app_color != self.app_color:
            self.app_color = app_color
            self.configure(bg=app_color)
            changed = True
        if seam_color and seam_color != self.seam_color:
            self.seam_color = seam_color
            changed = True
        if changed:
            self.redraw()

    def set_side(self, side: str) -> None:
        """Set whether the feather edge is on the 'left' or 'right' seam."""
        if side != self.side:
            self.side = side
            self.redraw()

    def _on_resize(self, event) -> None:
        if event.height > 0 and event.height != self._current_h:
            self._current_h = event.height
            self.redraw()

    def redraw(self) -> None:
        """Draw vertical slices that form the horizontal gradient."""
        self.delete("all")
        h = self.winfo_height() or self._current_h or 600
        w = self.feather_width

        # Direction:
        # If self.side == 'left', x=0 touches League Client (client_color),
        # blending to x=w which meets LeagueLoop app body (app_color).
        # If self.side == 'right', x=0 is LeagueLoop app body, x=w meets League Client.
        for x in range(w):
            factor = (x / float(max(1, w - 1)))
            if self.side == "left":
                col = interpolate_color(self.client_color, self.app_color, factor)
            else:
                col = interpolate_color(self.app_color, self.client_color, factor)
            self.create_line(x, 0, x, h, fill=col, width=1)

        # Draw an accent seam line at the border that directly touches the client
        if self.seam_color:
            seam_x = 0 if self.side == "left" else (w - 1)
            self.create_line(seam_x, 0, seam_x, h, fill=self.seam_color, width=1)
