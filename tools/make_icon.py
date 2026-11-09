"""
Generate the LeagueLoop application icon (Holiday / Winterblessed Edition).

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

For the Holiday / Winterblessed edition, the mark incorporates festive seasonal
accents while preserving its unmistakable silhouette at every size from 16px to
1024px:
- A Winterblessed frost aura and crystalline snowflakes in the dark Hextech tile
- A festive crimson-and-gold double rim with subtle corner holly-and-frost glow
- A jaunty crimson velvet Santa hat with plush snow-white fur trim and pom-pom
  perched on the upper-right arc of the golden cycle
- Twin emerald holly leaves and three glossy crimson berries tucked on the
  lower-left curve of the cycle

It is drawn at 4x and downsampled, which is what keeps the curves clean at
16px. Everything is proportional to `SIZE`, so no constant needs revisiting
if the geometry changes.

Palette combines the client's Hextech gold/teal with Snowdown crimson & pine:

    #0A162C  winter night hextech (tile, outer)
    #07101C  deeper midnight      (tile, inner)
    #C89B3C  gold                 (loop, low)
    #F8ECD4  warm parchment       (loop, high)
    #0AC8B9  hextech teal         (orb / frost glow)
    #EF3A3E  holiday crimson      (hat & berries, high)
    #94161C  deep velvet          (hat & berries, low)
    #2ABA5C  holly emerald        (leaves, high)
    #F8FAFC  snow white           (fur trim & pom-pom)
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

TILE_OUTER = (10, 22, 44, 255)      # #0A162C winter night hextech
TILE_INNER = (7, 16, 28, 255)       # #07101C deeper midnight
GOLD_LOW = (200, 155, 60, 255)      # #C89B3C
GOLD_HIGH = (248, 236, 212, 255)    # #F8ECD4
TEAL = (10, 200, 185, 255)          # #0AC8B9
FROST_BLUE = (186, 230, 253, 255)   # #BAE6FD winterblessed frost
CRIMSON_HIGH = (239, 58, 62, 255)   # #EF3A3E holiday velvet bright
CRIMSON_LOW = (148, 22, 28, 255)    # #94161C holiday velvet shadow
HOLLY_HIGH = (42, 186, 92, 255)     # #2ABA5C festive pine bright
HOLLY_LOW = (18, 107, 50, 255)      # #126B32 festive pine deep
SNOW_WHITE = (248, 250, 252, 255)   # #F8FAFC snow fur trim
SNOW_SHADE = (203, 213, 225, 255)   # #CBD5E1 snow fur shadow

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


def _draw_snowflake(draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float, color: tuple):
    """Draw a crisp 6-branch crystalline Winterblessed snowflake."""
    w_main = max(1, int(radius * 0.16))
    w_twig = max(1, int(radius * 0.12))
    for i in range(6):
        ang = math.radians(i * 60.0)
        ex = cx + radius * math.cos(ang)
        ey = cy + radius * math.sin(ang)
        draw.line([(cx, cy), (ex, ey)], fill=color, width=w_main)
        # Side crystal branches at 58% radius
        bx = cx + radius * 0.58 * math.cos(ang)
        by = cy + radius * 0.58 * math.sin(ang)
        twig_len = radius * 0.34
        for delta in (-45.0, 45.0):
            tang = ang + math.radians(delta)
            tx = bx + twig_len * math.cos(tang)
            ty = by + twig_len * math.sin(tang)
            draw.line([(bx, by), (tx, ty)], fill=color, width=w_twig)
    core_r = radius * 0.18
    draw.ellipse([cx - core_r, cy - core_r, cx + core_r, cy + core_r], fill=color)


def _draw_holly_cluster(size: int, cx: float, cy: float) -> Image.Image:
    """Render twin emerald holly leaves and three crimson berries at (cx, cy)."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    leaf_grad = _vertical_gradient(size, HOLLY_HIGH, HOLLY_LOW)

    # Two pointed holly leaves fanning toward bottom-left and top-left
    for leaf_angle in (148.0, 218.0):
        leaf_mask = Image.new("L", (size, size), 0)
        ldraw = ImageDraw.Draw(leaf_mask)
        ang = math.radians(leaf_angle)
        px, py = -math.sin(ang), math.cos(ang)
        length = size * 0.135
        width = size * 0.052
        # Scalloped holly leaf polygon
        pts = [
            (cx, cy),
            (cx + length * 0.30 * math.cos(ang) + width * 0.85 * px,
             cy + length * 0.30 * math.sin(ang) + width * 0.85 * py),
            (cx + length * 0.48 * math.cos(ang) + width * 0.52 * px,
             cy + length * 0.48 * math.sin(ang) + width * 0.52 * py),
            (cx + length * 0.68 * math.cos(ang) + width * 0.95 * px,
             cy + length * 0.68 * math.sin(ang) + width * 0.95 * py),
            (cx + length * math.cos(ang),
             cy + length * math.sin(ang)),
            (cx + length * 0.68 * math.cos(ang) - width * 0.95 * px,
             cy + length * 0.68 * math.sin(ang) - width * 0.95 * py),
            (cx + length * 0.48 * math.cos(ang) - width * 0.52 * px,
             cy + length * 0.48 * math.sin(ang) - width * 0.52 * py),
            (cx + length * 0.30 * math.cos(ang) - width * 0.85 * px,
             cy + length * 0.30 * math.sin(ang) - width * 0.85 * py),
        ]
        ldraw.polygon(pts, fill=255)

        # Soft drop shadow under each leaf
        shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        shadow.paste(
            Image.new("RGBA", (size, size), (0, 0, 0, 140)),
            (int(size * 0.006), int(size * 0.008)),
            leaf_mask.filter(ImageFilter.GaussianBlur(size * 0.010)),
        )
        layer.alpha_composite(shadow)
        layer.paste(leaf_grad, (0, 0), leaf_mask)

        # Gold-tinted leaf vein & rim highlight
        vdraw = ImageDraw.Draw(layer)
        vdraw.line(
            [(cx, cy), (cx + length * 0.82 * math.cos(ang), cy + length * 0.82 * math.sin(ang))],
            fill=(187, 247, 208, 190),
            width=max(1, int(size * 0.005)),
        )

    # Three glossy crimson holly berries clustered at the base
    berry_r = size * 0.028
    berry_offsets = [
        (-berry_r * 0.75, -berry_r * 0.45),
        (berry_r * 0.70, -berry_r * 0.25),
        (-berry_r * 0.05, berry_r * 0.78),
    ]
    bdraw = ImageDraw.Draw(layer)
    for dx, dy in berry_offsets:
        bx, by = cx + dx, cy + dy
        bdraw.ellipse(
            [bx - berry_r * 1.1, by - berry_r * 1.0, bx + berry_r * 1.2, by + berry_r * 1.3],
            fill=(15, 10, 20, 150),
        )
        bdraw.ellipse(
            [bx - berry_r, by - berry_r, bx + berry_r, by + berry_r],
            fill=CRIMSON_LOW,
        )
        inner_r = berry_r * 0.82
        bdraw.ellipse(
            [bx - inner_r, by - inner_r, bx + inner_r * 0.75, by + inner_r * 0.75],
            fill=CRIMSON_HIGH,
        )
        spec_r = berry_r * 0.30
        sx, sy = bx - berry_r * 0.32, by - berry_r * 0.32
        bdraw.ellipse(
            [sx - spec_r, sy - spec_r, sx + spec_r, sy + spec_r],
            fill=(255, 240, 240, 235),
        )

    return layer


def _draw_santa_hat(size: int, cx: float, cy: float) -> Image.Image:
    """Render a jaunty crimson velvet Santa hat with fluffy snow trim on the upper-right arc."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    crimson_grad = _vertical_gradient(size, CRIMSON_HIGH, CRIMSON_LOW)
    snow_grad = _vertical_gradient(size, SNOW_WHITE, SNOW_SHADE)

    # 1. Velvet red cap body sweeping from top-center over the upper-right arc
    cap_mask = Image.new("L", (size, size), 0)
    cdraw = ImageDraw.Draw(cap_mask)
    cap_pts = [
        (cx - size * 0.055, cy - size * 0.345),  # left base on ring
        (cx + size * 0.020, cy - size * 0.445),  # upper left rise
        (cx + size * 0.145, cy - size * 0.470),  # crown peak
        (cx + size * 0.275, cy - size * 0.425),  # upper slope toward tip
        (cx + size * 0.365, cy - size * 0.315),  # drooping right bend
        (cx + size * 0.380, cy - size * 0.205),  # pom-pom attachment tip
        (cx + size * 0.305, cy - size * 0.215),  # underside of drooping tip
        (cx + size * 0.255, cy - size * 0.265),  # right base on ring
        (cx + size * 0.110, cy - size * 0.320),  # mid-base curve
    ]
    cdraw.polygon(cap_pts, fill=255)
    cap_mask = cap_mask.filter(ImageFilter.GaussianBlur(size * 0.004)).point(
        lambda v: 255 if v > 110 else int(v * 2.2)
    )

    # Drop shadow beneath hat
    hat_shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hat_shadow.paste(
        Image.new("RGBA", (size, size), (0, 0, 0, 155)),
        (int(size * 0.008), int(size * 0.012)),
        cap_mask.filter(ImageFilter.GaussianBlur(size * 0.016)),
    )
    layer.alpha_composite(hat_shadow)
    layer.paste(crimson_grad, (0, 0), cap_mask)

    # Gold piping accent along the crown edge of the cap
    pdraw = ImageDraw.Draw(layer)
    pdraw.line(
        [
            (cx - size * 0.035, cy - size * 0.365),
            (cx + size * 0.030, cy - size * 0.435),
            (cx + size * 0.145, cy - size * 0.458),
            (cx + size * 0.265, cy - size * 0.415),
        ],
        fill=(255, 220, 160, 120),
        width=max(1, int(size * 0.008)),
    )

    # 2. Fluffy white fur brim along the base of the hat (overlapping puffs)
    brim_mask = Image.new("L", (size, size), 0)
    bdraw = ImageDraw.Draw(brim_mask)
    puff_steps = 9
    x0, y0 = cx - size * 0.065, cy - size * 0.340
    x1, y1 = cx + size * 0.265, cy - size * 0.245
    for i in range(puff_steps):
        t = i / (puff_steps - 1)
        # Slight upward arch along the ring curvature
        arch = math.sin(t * math.pi) * size * 0.024
        px = x0 + (x1 - x0) * t
        py = y0 + (y1 - y0) * t - arch
        pr = size * (0.036 if i in (0, puff_steps - 1) else 0.041)
        bdraw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=255)

    # Pom-pom at the drooping right tip
    pom_x, pom_y = cx + size * 0.375, cy - size * 0.185
    pom_r = size * 0.050
    for angle_deg in range(0, 360, 45):
        ang = math.radians(angle_deg)
        ox = pom_x + pom_r * 0.28 * math.cos(ang)
        oy = pom_y + pom_r * 0.28 * math.sin(ang)
        pr = pom_r * 0.78
        bdraw.ellipse([ox - pr, oy - pr, ox + pr, oy + pr], fill=255)

    brim_shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    brim_shadow.paste(
        Image.new("RGBA", (size, size), (5, 12, 24, 150)),
        (int(size * 0.005), int(size * 0.010)),
        brim_mask.filter(ImageFilter.GaussianBlur(size * 0.012)),
    )
    layer.alpha_composite(brim_shadow)
    layer.paste(snow_grad, (0, 0), brim_mask)

    # Bright snow highlight on top of brim and pom-pom
    hdraw = ImageDraw.Draw(layer)
    hdraw.ellipse(
        [pom_x - pom_r * 0.55, pom_y - pom_r * 0.65, pom_x + pom_r * 0.35, pom_y + pom_r * 0.25],
        fill=(255, 255, 255, 235),
    )

    return layer


def render(size: int = CANVAS) -> Image.Image:
    """Draw the holiday icon at `size` px square."""
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # ---- tile -----------------------------------------------------------
    radius = size * 0.22
    tile_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(tile_mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=255
    )

    tile = _vertical_gradient(size, TILE_OUTER, TILE_INNER)
    # Lift the centre with a Winterblessed teal-and-warm-gold aurora glow
    lift = Image.new("RGBA", (size, size), (24, 58, 88, 255))
    tile = Image.composite(lift, tile, _radial_falloff(size).point(
        lambda v: min(255, int(v * 0.62))
    ))

    # Subtle festive crimson warmth in the upper-right and emerald in lower-left
    frost_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(frost_layer)
    # Crystalline Winterblessed snowflakes & snow sparkles in the tile background
    snowflakes = [
        (size * 0.16, size * 0.18, size * 0.042, FROST_BLUE[:3] + (145,)),
        (size * 0.84, size * 0.80, size * 0.044, FROST_BLUE[:3] + (145,)),
        (size * 0.15, size * 0.52, size * 0.028, TEAL[:3] + (125,)),
        (size * 0.85, size * 0.50, size * 0.028, GOLD_HIGH[:3] + (125,)),
        (size * 0.50, size * 0.87, size * 0.030, FROST_BLUE[:3] + (120,)),
    ]
    for sx, sy, sr, scol in snowflakes:
        _draw_snowflake(fdraw, sx, sy, sr, scol)

    # Soft snowfall dots
    snow_dots = [
        (0.26, 0.12, 0.010), (0.11, 0.34, 0.008), (0.88, 0.34, 0.009),
        (0.72, 0.88, 0.010), (0.30, 0.86, 0.008), (0.82, 0.66, 0.007),
    ]
    for dx, dy, dr in snow_dots:
        r_dot = size * dr
        px, py = size * dx, size * dy
        fdraw.ellipse(
            [px - r_dot, py - r_dot, px + r_dot, py + r_dot],
            fill=(240, 249, 255, 145),
        )

    tile.alpha_composite(frost_layer)
    icon.paste(tile, (0, 0), tile_mask)

    # Festive dual rim: outer Hextech gold + inner icy holiday shimmer
    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rdraw = ImageDraw.Draw(rim)
    rdraw.rounded_rectangle(
        [size * 0.012, size * 0.012, size * (1 - 0.012), size * (1 - 0.012)],
        radius=radius * 0.94,
        outline=(212, 168, 72, 125),
        width=max(1, int(size * 0.009)),
    )
    rdraw.rounded_rectangle(
        [size * 0.026, size * 0.026, size * (1 - 0.026), size * (1 - 0.026)],
        radius=radius * 0.88,
        outline=(186, 230, 253, 55),
        width=max(1, int(size * 0.005)),
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

    # A warm gold-and-crimson holiday glow under the ring
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow.paste(gold, (0, 0), ring.filter(
        ImageFilter.GaussianBlur(size * 0.038)
    ).point(lambda v: int(v * 0.48)))
    icon.alpha_composite(glow)
    icon.paste(gold, (0, 0), ring)

    # ---- centre play glyph ----------------------------------------------
    play_r = size * 0.105
    play_mask = _play_triangle(size, cx, cy, play_r)

    play_glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    play_glow.paste(
        Image.new("RGBA", (size, size), TEAL[:3] + (135,)), (0, 0),
        play_mask.filter(ImageFilter.GaussianBlur(size * 0.030)),
    )
    icon.alpha_composite(play_glow)
    icon.paste(_vertical_gradient(size, GOLD_HIGH, GOLD_LOW), (0, 0), play_mask)

    # ---- holiday spirit overlays (holly cluster + Santa hat) -------------
    holly_layer = _draw_holly_cluster(size, cx - size * 0.215, cy + size * 0.225)
    icon.alpha_composite(holly_layer)

    hat_layer = _draw_santa_hat(size, cx, cy)
    icon.alpha_composite(hat_layer)

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
