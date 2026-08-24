"""
Generate the LeagueLoop application icon.

The icon is drawn here rather than stored as an opaque binary so it can be
re-rendered at any size, tweaked in one place, and reviewed as code. Run it
and every artwork file in `assets/` is rebuilt from this one definition.

    python tools/make_icon.py

Design
------
A dark rounded tile in the League client's own palette carrying a gold
**cycle**: a ring broken by two gaps and closed by two arrowheads, for the
loop the app automates — queue, draft, game, queue again. A solid gold play
triangle sits at the centre for the one action the whole app exists to take.

Two gaps rather than one, and a triangle rather than a dot, because the
previous mark relied on a single small teal orb to carry its meaning and that
orb is four pixels across at 16px. Two arrowheads read as *rotation* at any
size; a filled triangle reads as *play* at any size.

It is drawn at 8x and downsampled, which is what keeps the curves clean at
16px. Everything is proportional to `SIZE`, so no constant needs revisiting
if the geometry changes.

Palette is the client's, so the icon does not look foreign next to League on
a taskbar:

    #0A1428  hextech black (tile, outer)
    #071019  deeper black (tile, inner)
    #C89B3C  gold          (loop, low)
    #F0E6D2  parchment     (loop, high)
    #0AC8B9  teal          (orb)
"""
from __future__ import annotations

import hashlib
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# Rendered at this size, then downsampled to each icon size.
SIZE = 1024
SS = 4  # supersampling factor for the master render
CANVAS = SIZE * SS

TILE_OUTER = (10, 20, 40, 255)     # #0A1428
TILE_INNER = (7, 16, 25, 255)      # #071019
GOLD_LOW = (200, 155, 60, 255)     # #C89B3C
GOLD_HIGH = (240, 230, 210, 255)   # #F0E6D2
TEAL = (10, 200, 185, 255)         # #0AC8B9

#: Sizes embedded in the .ico. 256 and 48 are the ones Windows actually
#: shows most often; 16 is the one that punishes a fussy design.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _vertical_gradient(size, top, bottom):
    """A one-pixel-wide gradient stretched across the canvas."""
    strip = Image.new("RGBA", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        strip.putpixel((0, y), tuple(
            round(top[i] + (bottom[i] - top[i]) * t) for i in range(4)
        ))
    return strip.resize((size, size), Image.BICUBIC)


def _radial_falloff(size, inner=0.0, outer=0.75):
    """A soft centre-bright mask, for lifting the middle of the tile."""
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    steps = 64
    for i in range(steps, 0, -1):
        t = i / steps
        r = size * 0.5 * (inner + (outer - inner) * t)
        value = round(255 * (1.0 - t) ** 1.6)
        draw.ellipse(
            [size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r],
            fill=value,
        )
    return mask.filter(ImageFilter.GaussianBlur(size * 0.05))


def _ring_mask(size, cx, cy, r_outer, r_inner, gap_start, gap_end):
    """An annulus with a wedge removed, as a mask."""
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=255)
    draw.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill=0)
    # Knock the gap out with a generous wedge so the cut is clean.
    reach = r_outer * 3
    points = [(cx, cy)]
    steps = 48
    for i in range(steps + 1):
        a = math.radians(gap_start + (gap_end - gap_start) * i / steps)
        points.append((cx + reach * math.cos(a), cy + reach * math.sin(a)))
    draw.polygon(points, fill=0)
    return mask


def _arrowhead(size, cx, cy, radius, angle_deg, length, width):
    """A triangular head sitting on the ring, pointing along its tangent."""
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    a = math.radians(angle_deg)
    # Tangent direction for a clockwise loop.
    tx, ty = -math.sin(a), math.cos(a)
    nx, ny = math.cos(a), math.sin(a)
    bx, by = cx + radius * nx, cy + radius * ny
    tip = (bx + tx * length, by + ty * length)
    left = (bx + nx * width, by + ny * width)
    right = (bx - nx * width, by - ny * width)
    draw.polygon([tip, left, right], fill=255)
    return mask


def _play_triangle(size, cx, cy, radius):
    """An equilateral play glyph, optically centred.

    A triangle centred on its bounding box looks left-heavy, because the mass
    sits behind the tip. Nudging it right by an eighth of its radius is what
    makes it look centred.
    """
    mask = Image.new("L", (size, size), 0)
    cx += radius * 0.12
    points = []
    for angle in (0.0, 120.0, 240.0):
        a = math.radians(angle)
        points.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask


def render(size: int = CANVAS) -> Image.Image:
    """Draw the icon at `size` px square."""
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # ---- tile -----------------------------------------------------------
    radius = size * 0.22
    tile_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(tile_mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=255
    )

    tile = _vertical_gradient(size, TILE_OUTER, TILE_INNER)
    # Lift the centre very slightly so the tile does not read as flat black.
    lift = Image.new("RGBA", (size, size), (26, 48, 76, 255))
    tile = Image.composite(lift, tile, _radial_falloff(size).point(
        lambda v: min(255, int(v * 0.55))
    ))
    icon.paste(tile, (0, 0), tile_mask)

    # A hairline gold rim, the way the client edges its own panels.
    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle(
        [size * 0.012, size * 0.012, size * (1 - 0.012), size * (1 - 0.012)],
        radius=radius * 0.94,
        outline=(200, 155, 60, 90),
        width=max(1, int(size * 0.008)),
    )
    icon.alpha_composite(rim)

    # ---- the cycle -------------------------------------------------------
    cx = cy = size / 2
    r_outer = size * 0.360
    r_inner = size * 0.268

    gold = _vertical_gradient(size, GOLD_HIGH, GOLD_LOW)

    # Two gaps, opposite each other, each closed by an arrowhead. Rotational
    # symmetry is what makes this read as a cycle rather than as a letter.
    ring = _ring_mask(size, cx, cy, r_outer, r_inner, -14.0, 46.0)
    ring = ImageChops.darker(
        ring, _ring_mask(size, cx, cy, r_outer * 3, 0, 166.0, 226.0)
    )

    mid = (r_outer + r_inner) / 2
    for angle in (46.0, 226.0):
        ring = ImageChops.lighter(ring, _arrowhead(
            size, cx, cy, radius=mid, angle_deg=angle,
            # Kept inside the ring's own radius. A longer head escapes the
            # disc and the mark stops reading as a loop.
            length=size * 0.100,
            width=(r_outer - r_inner) * 1.02,
        ))

    # A soft gold glow under the ring reads as the client's own bloom.
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow.paste(gold, (0, 0), ring.filter(
        ImageFilter.GaussianBlur(size * 0.035)
    ).point(lambda v: int(v * 0.42)))
    icon.alpha_composite(glow)
    icon.paste(gold, (0, 0), ring)

    # ---- centre play glyph ----------------------------------------------
    play_r = size * 0.105
    play_mask = _play_triangle(size, cx, cy, play_r)

    play_glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    play_glow.paste(
        Image.new("RGBA", (size, size), TEAL[:3] + (110,)), (0, 0),
        play_mask.filter(ImageFilter.GaussianBlur(size * 0.028)),
    )
    icon.alpha_composite(play_glow)
    icon.paste(_vertical_gradient(size, GOLD_HIGH, GOLD_LOW), (0, 0), play_mask)

    return icon


def build(assets_dir: str) -> list:
    """Render every artwork file the app and the shortcuts need."""
    os.makedirs(assets_dir, exist_ok=True)
    master = render(CANVAS).resize((SIZE, SIZE), Image.LANCZOS)

    written = []

    def save(name, image):
        path = os.path.join(assets_dir, name)
        image.save(path)
        written.append(path)

    # The .ico Windows uses for the executable, the shortcut and the taskbar.
    #
    # Explorer caches a shortcut's icon against the **(path, index)** pair, so
    # rewriting `leagueloop.ico` in place leaves the *previous* artwork on the
    # desktop until the user rebuilds the icon cache or logs out. Overwriting
    # is therefore not enough to change an icon anyone can see.
    #
    # So the shortcut points at a filename that changes when the artwork does:
    # `icon-<8 hex>.ico`, where the hex is a digest of the rendered pixels.
    # A path Explorer has never seen cannot be served from its cache. Identical
    # artwork produces an identical name, so re-running this does not litter.
    for name in ("app.ico", "leagueloop.ico"):
        ico_path = os.path.join(assets_dir, name)
        master.save(ico_path, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
        written.append(ico_path)

    digest = hashlib.sha256(master.tobytes()).hexdigest()[:8]
    stamped = os.path.join(assets_dir, "icon-{}.ico".format(digest))
    master.save(stamped, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    written.append(stamped)

    # Previous stamped icons are dead weight and, worse, a shortcut still
    # pointing at one would keep showing old artwork.
    for existing in sorted(os.listdir(assets_dir)):
        if (existing.startswith("icon-") and existing.endswith(".ico")
                and existing != os.path.basename(stamped)):
            try:
                os.remove(os.path.join(assets_dir, existing))
            except OSError:
                pass

    # PNGs the shell and the tray load by name.
    save("icon.png", master.resize((512, 512), Image.LANCZOS))
    save("app.png", master.resize((512, 512), Image.LANCZOS))
    save("app_icon.png", master)
    save("logo.png", master)

    # The tray uses a distinct idle/active pair. Same mark, so it is still
    # recognisably the app; the idle one greys the play glyph, because at
    # 16px a colour change is the only difference anyone can actually see.
    save("icon_active.png", master.resize((256, 256), Image.LANCZOS))

    idle = master.copy()
    idle.paste(
        Image.new("RGBA", idle.size, (120, 134, 150, 255)), (0, 0),
        _play_triangle(SIZE, SIZE / 2, SIZE / 2, SIZE * 0.105),
    )
    save("icon_idle.png", idle.resize((256, 256), Image.LANCZOS))

    return written


def shortcut_icon(assets_dir: str) -> str:
    """The .ico a shortcut should point at.

    The content-stamped one when it exists, so a rebuilt shortcut always gets
    a path Explorer has not cached; `leagueloop.ico` otherwise.
    """
    try:
        stamped = sorted(
            name for name in os.listdir(assets_dir)
            if name.startswith("icon-") and name.endswith(".ico")
        )
    except OSError:
        stamped = []
    if stamped:
        return os.path.join(assets_dir, stamped[-1])
    return os.path.join(assets_dir, "leagueloop.ico")


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets = os.path.join(root, "assets")
    for path in build(assets):
        print("wrote", os.path.relpath(path, root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
