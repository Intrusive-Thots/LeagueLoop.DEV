"""Small, consistent UI glyphs drawn at runtime with PIL.

Emoji render differently (or not at all) across Windows, Linux and font
fallbacks, so chrome icons — tabs, header controls, empty states — are drawn
here as simple line icons. Each glyph is drawn at 4x and downsampled so the
strokes stay crisp at 14–28 px.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Tuple

from PIL import Image, ImageDraw
from utils.logger import Logger

_SCALE = 4


def _hex(c: str) -> Tuple[int, int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255


def _draw(name: str, d: ImageDraw.ImageDraw, s: int, col, w: int) -> None:
    """Draw glyph *name* on a canvas of side *s* with stroke width *w*."""
    m = s * 0.14  # outer margin
    if name == "play":
        d.polygon([(s * .30, s * .18), (s * .30, s * .82), (s * .82, s * .50)], fill=col)
    elif name == "chest":
        d.rounded_rectangle([m, s * .34, s - m, s * .84], radius=s * .06, outline=col, width=w)
        d.arc([m, s * .12, s - m, s * .58], 180, 360, fill=col, width=w)
        d.line([m, s * .48, s - m, s * .48], fill=col, width=w)
        d.rectangle([s * .44, s * .42, s * .56, s * .58], fill=col)
    elif name == "person":
        d.ellipse([s * .34, s * .12, s * .66, s * .44], outline=col, width=w)
        d.arc([s * .16, s * .52, s * .84, s * 1.16], 180, 360, fill=col, width=w)
        d.line([s * .16, s * .84, s * .84, s * .84], fill=col, width=w)
    elif name == "bolt":
        d.polygon([(s * .58, s * .08), (s * .22, s * .56), (s * .48, s * .56),
                   (s * .40, s * .92), (s * .78, s * .42), (s * .52, s * .42)], fill=col)
    elif name == "gear":
        import math
        cx = cy = s / 2
        for i in range(8):
            a = i * math.pi / 4
            x, y = cx + math.cos(a) * s * .36, cy + math.sin(a) * s * .36
            d.ellipse([x - s * .08, y - s * .08, x + s * .08, y + s * .08], fill=col)
        d.ellipse([cx - s * .30, cy - s * .30, cx + s * .30, cy + s * .30], fill=col)
        d.ellipse([cx - s * .13, cy - s * .13, cx + s * .13, cy + s * .13], fill=(0, 0, 0, 0))
    elif name in ("lock", "unlock"):
        d.rounded_rectangle([s * .22, s * .46, s * .78, s * .86], radius=s * .06, fill=col)
        if name == "lock":
            d.arc([s * .32, s * .16, s * .68, s * .64], 180, 360, fill=col, width=w)
            d.line([s * .32, s * .40, s * .32, s * .48], fill=col, width=w)
            d.line([s * .68, s * .40, s * .68, s * .48], fill=col, width=w)
        else:
            d.arc([s * .46, s * .10, s * .82, s * .58], 180, 360, fill=col, width=w)
            d.line([s * .46, s * .34, s * .46, s * .48], fill=col, width=w)
    elif name == "minimize":
        d.line([s * .24, s * .62, s * .76, s * .62], fill=col, width=w)
    elif name == "close":
        d.line([s * .26, s * .26, s * .74, s * .74], fill=col, width=w)
        d.line([s * .74, s * .26, s * .26, s * .74], fill=col, width=w)
    elif name == "refresh":
        d.arc([s * .18, s * .18, s * .82, s * .82], 40, 330, fill=col, width=w)
        d.polygon([(s * .66, s * .10), (s * .86, s * .30), (s * .60, s * .36)], fill=col)
    elif name == "link":
        d.rounded_rectangle([s * .08, s * .34, s * .56, s * .66], radius=s * .16, outline=col, width=w)
        d.rounded_rectangle([s * .44, s * .34, s * .92, s * .66], radius=s * .16, outline=col, width=w)
    elif name == "plus":
        d.line([s * .50, s * .20, s * .50, s * .80], fill=col, width=w)
        d.line([s * .20, s * .50, s * .80, s * .50], fill=col, width=w)
    elif name == "launch":  # arrow leaving a box: "open external app"
        d.line([s * .40, s * .20, s * .20, s * .20, s * .20, s * .80, s * .80, s * .80, s * .80, s * .60],
               fill=col, width=w, joint="curve")
        d.line([s * .46, s * .54, s * .82, s * .18], fill=col, width=w)
        d.polygon([(s * .56, s * .14), (s * .86, s * .14), (s * .86, s * .44)], fill=col)
    elif name == "warning":
        d.polygon([(s * .50, s * .12), (s * .90, s * .84), (s * .10, s * .84)], outline=col, width=w)
        d.line([s * .50, s * .38, s * .50, s * .60], fill=col, width=w)
        d.ellipse([s * .46, s * .67, s * .54, s * .75], fill=col)
    elif name == "chev_right":
        d.line([s * .40, s * .26, s * .64, s * .50, s * .40, s * .74], fill=col, width=w, joint="curve")
    elif name == "chev_down":
        d.line([s * .26, s * .40, s * .50, s * .64, s * .74, s * .40], fill=col, width=w, joint="curve")
    elif name == "chev_up":
        d.line([s * .26, s * .60, s * .50, s * .36, s * .74, s * .60], fill=col, width=w, joint="curve")
    elif name == "pencil":  # angled pencil body + tip
        d.polygon([(s * .62, s * .16), (s * .84, s * .38), (s * .38, s * .84),
                   (s * .16, s * .84), (s * .16, s * .62)], outline=col, width=w)
        d.line([s * .52, s * .26, s * .74, s * .48], fill=col, width=w)
    elif name == "check":
        d.line([s * .22, s * .52, s * .42, s * .72, s * .80, s * .30], fill=col, width=w, joint="curve")
    elif name == "swords":  # crossed blades: "match"
        d.line([s * .14, s * .14, s * .70, s * .70], fill=col, width=w)  # blades
        d.line([s * .86, s * .14, s * .30, s * .70], fill=col, width=w)
        d.line([s * .54, s * .78, s * .78, s * .54], fill=col, width=w)  # guards
        d.line([s * .22, s * .54, s * .46, s * .78], fill=col, width=w)
        d.line([s * .70, s * .70, s * .88, s * .88], fill=col, width=w)  # grips
        d.line([s * .30, s * .70, s * .12, s * .88], fill=col, width=w)
    elif name == "trash":  # lid, handle, tapered bin with two ribs
        d.line([s * .18, s * .26, s * .82, s * .26], fill=col, width=w)
        d.line([s * .40, s * .26, s * .42, s * .14, s * .58, s * .14, s * .60, s * .26], fill=col, width=w)
        d.polygon([(s * .26, s * .32), (s * .74, s * .32), (s * .68, s * .86), (s * .32, s * .86)],
                  outline=col, width=w)
        d.line([s * .44, s * .44, s * .45, s * .74], fill=col, width=w)
        d.line([s * .56, s * .44, s * .55, s * .74], fill=col, width=w)
    else:
        raise KeyError(name)


@lru_cache(maxsize=128)
def glyph_image(name: str, color: str = "#F0E6D2", size: int = 16) -> Image.Image:
    """Return an RGBA PIL image of glyph *name* in *color* at *size* px."""
    s = size * _SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = max(_SCALE, int(round(s * 0.09)))
    _draw(name, d, s, _hex(color), w)
    return img.resize((size, size), Image.LANCZOS)


def ctk_glyph(name: str, color: str = "#F0E6D2", size: int = 16):
    """Return a CTkImage for *name* (import is local so PIL-only callers work)."""
    import customtkinter as ctk  # type: ignore
    img = glyph_image(name, color, size)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


GLYPHS = ("play", "chest", "person", "bolt", "gear", "lock", "unlock",
          "minimize", "close", "refresh", "link", "plus", "launch", "warning",
          "chev_right", "chev_down", "chev_up", "pencil", "check", "swords", "trash")


def set_icon(btn, name: str, color: str, size: int = 14) -> None:
    """Put glyph *name* left of *btn*'s text (CTkButton or RiotButton)."""
    target = getattr(btn, "lbl", btn)  # RiotButton draws its text in .lbl
    try:
        target.configure(image=ctk_glyph(name, color, size), compound="left")
        btn._ll_icon = (name, color, size)  # lets disabled state recolour it (#24)
    except Exception as exc:
        Logger.debug("Glyphs", "set_icon suppressed an error", exc=exc)


def set_chevron(label, expanded: bool, color: str = "#C8AA6E", size: int = 12) -> None:
    """Drawn disclosure chevron left of a section label; strips old ▶/▼ text."""
    try:
        text = str(label.cget("text")).lstrip("▶▼ ").strip()
        label.configure(text=f" {text}" if text else "", compound="left",
                        image=ctk_glyph("chev_down" if expanded else "chev_right", color, size))
    except Exception as exc:
        Logger.debug("Glyphs", "set_chevron suppressed an error", exc=exc)
