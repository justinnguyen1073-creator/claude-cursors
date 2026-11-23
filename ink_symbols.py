"""Text caret and resize arrows drawn with the Duet ink brush.

Each symbol is a few strokes in a -50..50 box, drawn with `duet.brush` in black ink on a
thin cream edge (so it still shows on dark windows). The brush "boils" (its hand-drawn
wobble steps between four variants) so the symbols keep moving like the rest of the theme.
"""
import math

import cairo

import duet

CREAM = (0xFA / 255, 0xF9 / 255, 0xF5 / 255)
BOIL_STEPS = 24  # wobble changes per loop (every other frame)
# Symbol sizes, tuned so at the same size setting they match Cursor Cursors and Volantes:
# a 17 px tall caret and 21 px long arrows at size 24.
SCALE = {"text": 0.643, "vertical-text": 0.643}
ARROW_SCALE = 0.798
WEIGHT = 0.047   # stroke width as a fraction of the cursor size


def _line(a, b, n=40):
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def _poly(*pts, n=24):
    out = []
    for a, b in zip(pts, pts[1:]):
        seg = _line(a, b, n)
        out.extend(seg if not out else seg[1:])
    return out


def _curve(a, c, b, n=30):
    """Quadratic curve from a to b bending toward c."""
    return [((1 - t) ** 2 * a[0] + 2 * t * (1 - t) * c[0] + t * t * b[0],
             (1 - t) ** 2 * a[1] + 2 * t * (1 - t) * c[1] + t * t * b[1])
            for t in (i / n for i in range(n + 1))]


def _rotate(strokes, deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return [[(x * c - y * s, x * s + y * c) for x, y in st] for st in strokes]


def ibeam():
    return [
        _line((0, -31), (0, 31)),
        _curve((-11, -36), (-2, -34), (0, -30)) + _curve((0, -30), (2, -34), (11, -36))[1:],
        _curve((-11, 36), (-2, 34), (0, 30)) + _curve((0, 30), (2, 34), (11, 36))[1:],
    ]


def double_arrow():
    """Horizontal two-headed arrow."""
    L, head, spread = 36, 13, 11
    return [
        _line((-L + 2, 0), (L - 2, 0)),
        _poly((-L + head, -spread), (-L, 0), (-L + head, spread)),
        _poly((L - head, -spread), (L, 0), (L - head, spread)),
    ]


def split_arrow():
    """Two arrows pointing apart from a double bar (column resize)."""
    head, spread = 11, 10
    return [
        _line((-4, -24), (-4, 24)),
        _line((4, -24), (4, 24)),
        _line((-11, 0), (-37, 0)),
        _poly((-37 + head, -spread), (-37, 0), (-37 + head, spread)),
        _line((11, 0), (37, 0)),
        _poly((37 - head, -spread), (37, 0), (37 - head, spread)),
    ]


SYMBOLS = {
    "text": lambda: ibeam(),
    "vertical-text": lambda: _rotate(ibeam(), 90),
    "size_hor": lambda: double_arrow(),
    "size_ver": lambda: _rotate(double_arrow(), 90),
    "size_fdiag": lambda: _rotate(double_arrow(), 45),
    "size_bdiag": lambda: _rotate(double_arrow(), -45),
    "col-resize": lambda: split_arrow(),
    "row-resize": lambda: _rotate(split_arrow(), 90),
}


def render(size, u, name, blur):
    """Cairo surface of symbol `name` at loop time u. `blur(surface, r)` makes the shadow."""
    k = SCALE.get(name, ARROW_SCALE)
    strokes = [[(x * k, y * k) for x, y in st] for st in SYMBOLS[name]()]
    unit = size / 100  # px per box unit
    width = max(1.4, size * WEIGHT) / unit
    halo = max(1.0, size / 30) / unit
    boil = duet.BOIL[int(math.floor(u * BOIL_STEPS)) % 4]
    paths = [duet.brush(st, width, 1.3 + i * 2.1, boil, duet.TAU * u) for i, st in enumerate(strokes)]

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    shadow = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx, sctx = cairo.Context(surf), cairo.Context(shadow)
    for c, dy in ((ctx, 0), (sctx, 0.02 * size)):
        c.set_antialias(cairo.ANTIALIAS_BEST)
        c.translate(size / 2, size / 2 + dy)
        c.scale(unit, unit)
        c.set_line_join(cairo.LINE_JOIN_ROUND)
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        c.set_line_width(2 * halo)

    sctx.set_source_rgba(0, 0, 0, 1)
    for p in paths:
        duet.trace(sctx, p)
        sctx.fill_preserve()
        sctx.stroke()
    ctx.save()
    ctx.identity_matrix()
    ctx.set_source_surface(blur(shadow, max(1, size // 28)), 0, 0)
    ctx.paint_with_alpha(0.35)
    ctx.restore()

    ctx.set_source_rgb(*CREAM)
    for p in paths:
        duet.trace(ctx, p)
        ctx.fill_preserve()
        ctx.stroke()
    ctx.set_source_rgb(*duet.INK)
    for p in paths:
        duet.trace(ctx, p)
        ctx.fill()
    surf.flush()
    return surf
