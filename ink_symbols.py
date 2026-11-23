"""Caret, arrows, and tool cursors drawn with the Duet ink brush.

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
WIDTH_MUL = {"cell": 1.6}  # symbols drawn with a heavier stroke
# Cream-filled circles (center x, y, radius in box units) drawn under the ink: magnifier lenses.
FILLS = {"zoom-in": [(-8, -8, 21)], "zoom-out": [(-8, -8, 21)]}
# Click points in box units (before scaling); symbols not listed click at their center.
HOTSPOT = {}


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


def _arcpts(cx, cy, r, a0, a1, n=48):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def crosshair():
    g = 11  # gap around the click point
    return [_line((0, -36), (0, -g)), _line((0, g), (0, 36)),
            _line((-36, 0), (-g, 0)), _line((g, 0), (36, 0))]


def cell():
    return [_line((-20, 0), (20, 0)), _line((0, -20), (0, 20))]


_DIAG = (1 / math.sqrt(2), -1 / math.sqrt(2))   # toward the upper right
_PERP = (1 / math.sqrt(2), 1 / math.sqrt(2))
_TIP = (-30, 30)                                 # tools click with their tip, lower left


def _along(t, side=0.0):
    return (_TIP[0] + _DIAG[0] * t + _PERP[0] * side, _TIP[1] + _DIAG[1] * t + _PERP[1] * side)


def pencil():
    w = 7
    return [
        _poly(_along(0), _along(14, w), _along(62, w), _along(62, -w), _along(14, -w), _along(0)),
        _line(_along(14, w), _along(14, -w), 12),
        _line(_along(51, w), _along(51, -w), 12),
    ]


def color_picker():
    c = _along(52)
    return [
        _line(_along(0), _along(12), 12),
        _poly(_along(12, 4), _along(40, 4), _along(40, -4), _along(12, -4), _along(12, 4)),
        _arcpts(c[0], c[1], 10, 0, 360),
    ]


def zoom(plus):
    cx = cy = -8
    hx, hy = 1 / math.sqrt(2), 1 / math.sqrt(2)
    out = [_arcpts(cx, cy, 21, 0, 360),
           _line((cx + hx * 21, cy + hy * 21), (cx + hx * 46, cy + hy * 46)),
           _line((cx - 10, cy), (cx + 10, cy))]
    if plus:
        out.append(_line((cx, cy - 10), (cx, cy + 10)))
    return out


def arrow_up():
    return [_line((0, 34), (0, -33)), _poly((-12, -21), (0, -35), (12, -21))]


def to_edge_up():
    """Arrow pointing up into a bar (resize from the top edge)."""
    return [_line((-26, -34), (26, -34)), _line((0, 32), (0, -22)), _poly((-11, -11), (0, -24), (11, -11))]


def to_corner():
    """Arrow pointing into the top-left corner."""
    return [_poly((-34, -6), (-34, -34), (-6, -34)), _line((26, 26), (-22, -22)),
            _poly((-24, -8), (-24, -24), (-8, -24))]


def tee_top():
    return [_line((-26, -30), (26, -30)), _line((0, -30), (0, 34))]


def dotbox():
    return [_poly((-24, -24), (24, -24), (24, 24), (-24, 24), (-24, -24)), _line((0, 0), (0.4, 0), 2)]


def draft():
    """A loopy line like Duet's thinking ink."""
    pts = []
    for i in range(161):
        e = i / 160
        n = 9 * math.sin(math.pi * e) ** 0.8
        r = 2 * math.pi * 1.5 * e
        pts.append((-34 + 68 * e + n * math.sin(r), 6 - n * (1 - math.cos(r))))
    return [pts]


def _rot_pt(p, deg):
    r = math.radians(deg)
    return (p[0] * math.cos(r) - p[1] * math.sin(r), p[0] * math.sin(r) + p[1] * math.cos(r))


for _name, _pt in (("pencil", _TIP), ("color-picker", _TIP), ("zoom-in", (-8, -8)), ("zoom-out", (-8, -8))):
    HOTSPOT[_name] = _pt
for _deg, _a, _e, _c, _t in ((0, "up-arrow", "top_side", "top_left_corner", "top_tee"),
                             (90, "right-arrow", "right_side", "top_right_corner", "right_tee"),
                             (180, "down-arrow", "bottom_side", "bottom_right_corner", "bottom_tee"),
                             (270, "left-arrow", "left_side", "bottom_left_corner", "left_tee")):
    HOTSPOT[_a] = _rot_pt((0, -35), _deg)
    HOTSPOT[_e] = _rot_pt((0, -34), _deg)
    HOTSPOT[_c] = _rot_pt((-34, -34), _deg)
    HOTSPOT[_t] = _rot_pt((0, -30), _deg)


SYMBOLS = {
    "crosshair": crosshair,
    "cell": cell,
    "pencil": pencil,
    "color-picker": color_picker,
    "zoom-in": lambda: zoom(True),
    "zoom-out": lambda: zoom(False),
    "dotbox": dotbox,
    "draft": draft,
    **{name: (lambda d=deg: _rotate(arrow_up(), d)) for deg, name in
       ((0, "up-arrow"), (90, "right-arrow"), (180, "down-arrow"), (270, "left-arrow"))},
    **{name: (lambda d=deg: _rotate(to_edge_up(), d)) for deg, name in
       ((0, "top_side"), (90, "right_side"), (180, "bottom_side"), (270, "left_side"))},
    **{name: (lambda d=deg: _rotate(to_corner(), d)) for deg, name in
       ((0, "top_left_corner"), (90, "top_right_corner"), (180, "bottom_right_corner"), (270, "bottom_left_corner"))},
    **{name: (lambda d=deg: _rotate(tee_top(), d)) for deg, name in
       ((0, "top_tee"), (90, "right_tee"), (180, "bottom_tee"), (270, "left_tee"))},
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
    width = max(1.4, size * WEIGHT) * WIDTH_MUL.get(name, 1.0) / unit
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
    for x, y, r in FILLS.get(name, []):
        ctx.new_path()
        ctx.arc(x * k, y * k, r * k, 0, 2 * math.pi)
        ctx.fill()
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


def hotspot(size, name):
    """Click point in pixels for symbol `name` on a size x size canvas."""
    k = SCALE.get(name, ARROW_SCALE)
    x, y = HOTSPOT.get(name, (0, 0))
    unit = size / 100
    return (max(0, min(size - 1, round(size / 2 + x * k * unit))),
            max(0, min(size - 1, round(size / 2 + y * k * unit))))
