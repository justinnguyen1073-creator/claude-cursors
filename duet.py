"""Claude Duet's mascot: an ink ring orbiting the clay blob, for the busy cursors.

Sources:
- The brush (`brush`) and blob wobble are ported from the Claude desktop app's Duet code.
- The orbit is the desktop app's "year" ring: a tilted ellipse around the blob whose back
  half passes behind it. A stretch of the ring travels around the blob twice per loop.
- The symbol badges' write-on easing follows the claude.com Duet demo
  (claude.com/_next/static/chunks/f823c1ee2fa7fe75.js), where a new line writes in from
  its start over ~565 ms.

Every periodic term completes a whole number of cycles per LOOP, so the cursor repeats
seamlessly. Coordinates are viewBox units with the blob centered at (0, 0), radius ~18.
"""
import math

TAU = math.pi * 2
H_ = 0.5
SEED = 1.66
INK_WIDTH = 3.94
RING_WIDTH = 3.2
BOIL = [[0, 0, 0, 0], [1.9, 2.7, 1.3, 3.1], [3.8, 5.1, 2.9, 0.7], [5.3, 1.1, 4.6, 2.2]]

CLAY = (0xD9 / 255, 0x77 / 255, 0x57 / 255)
INK = (0x14 / 255, 0x14 / 255, 0x13 / 255)

LOOP = 3.36           # seconds; 48 frames at 70 ms, the same loop as the spark
ORBIT_RADIUS = 18.5

# Everything drawn fits in this box (ring, blob plus wobble, brush width).
BOUNDS = (-37.0, -22.0, 37.0, 22.0)


def _cyc(t, period):
    """Phase in turns for `period` seconds, snapped so it repeats exactly each LOOP."""
    n = max(1, round(LOOP / period))
    return t / LOOP * n


def _clamp(e):
    return 0.0 if e < 0 else 1.0 if e > 1 else e


def _smooth(e):
    t = _clamp(e)
    return t * t * (3 - 2 * t)


def _write_ease(t):
    t = _clamp(t)
    return 0.45 * _smooth(t) + 0.55 * (1 - (1 - t) ** 3)


def _fract(e):
    return e - math.floor(e)


def _hash(e, t):
    return _fract(math.sin(e * 127.1 + t * 311.7) * 43758.5453)


# ---- the ring: centerline point at e in [0, 1] and time t ----

RING_TILT = -0.3
RING_ARC = 0.62  # how much of the ring is drawn at once


def _ring_angle(e, t):
    # the drawn arc travels around once every ~1.68 s
    return TAU * (e * RING_ARC + _cyc(t, 1.68))


def orbit_point(e, t):
    a = _ring_angle(e, t)
    x, y = 33 * math.cos(a), 10.5 * math.sin(a)
    c, s = math.cos(RING_TILT), math.sin(RING_TILT)
    return (x * c - y * s, x * s + y * c)


def orbit_behind(e, t):
    return math.sin(_ring_angle(e, t)) < 0  # the far half of the ring


# ---- brush (ported from the desktop app) ----

def _taper(seed, end, width, total):
    i = _hash(seed, end * 7.31 + 1.7)
    a = _hash(seed, end * 3.17 + 5.3)
    return dict(f=0.97 - 0.12 * i,
                len=min(width * (0.7 + 0.9 * i) * (0.9 + 0.2 * a), 0.45 * total),
                p=1.7 + 0.6 * a)


def _taper_at(dist, tp):
    n = min(1.0, dist / tp["len"])
    return tp["f"] + (1 - tp["f"]) * (1 - (1 - n) ** tp["p"])


def _quad_chain(path, pts):
    for n in range(1, len(pts) - 1):
        mid = ((pts[n][0] + pts[n + 1][0]) / 2, (pts[n][1] + pts[n + 1][1]) / 2)
        path.append(("Q", pts[n][0], pts[n][1], mid[0], mid[1]))
    path.append(("L", pts[-1][0], pts[-1][1]))


def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy) or 1
    return dx / d, dy / d


def brush(pts, width, seed, boil, edge_phase):
    """The app's brush: closed outline of a tapered, wobbling ink stroke along pts."""
    path = []
    a = len(pts)
    cum = [0.0]
    for t in range(1, a):
        cum.append(cum[-1] + math.hypot(pts[t][0] - pts[t - 1][0], pts[t][1] - pts[t - 1][1]))
    s = cum[-1]
    if a < 2 or s < 0.8:
        path.append(("circle", pts[0][0], pts[0][1], max(0.4, width / 2)))
        return path
    c = min(1, s / (90 * H_))
    l_amp = 6 * 0.3 * H_ * c
    u_amp = 0.35 * H_ * c
    d = TAU / (300 * H_)
    f = TAU / (170 * H_)
    p = TAU / (70 * H_)
    g = TAU / (120 * H_)
    k5 = TAU / (50 * H_)
    tv = _taper(seed, 0, width, s)
    ty = _taper(seed, 1, width, s)
    left, right, half = [], [], []
    for i in range(a):
        m = pts[max(0, i - 1)]
        h = pts[min(a - 1, i + 1)]
        dx, dy = h[0] - m[0], h[1] - m[1]
        tl = math.hypot(dx, dy) or 1
        nx, ny = -dy / tl, dx / tl
        o = cum[i]
        k = _taper_at(o, tv) * _taper_at(s - o, ty)
        off = (l_amp * (0.65 * math.sin(f * o + boil[0] + seed) + 0.35 * math.sin(p * o + boil[1] + seed * 1.7))
               + u_amp * math.sin(d * o + edge_phase + seed * 2.3))
        j = 0.6 * math.sin(g * o + boil[2] + seed * 0.9) + 0.4 * math.sin(k5 * o + boil[3] + seed * 1.3)
        mw = max(0.3, width * (1 + 0.26 * j) * k) / 2
        left.append((pts[i][0] + nx * (off + mw), pts[i][1] + ny * (off + mw)))
        right.append((pts[i][0] + nx * (off - mw), pts[i][1] + ny * (off - mw)))
        half.append(mw)
    right.reverse()
    ce = half[a - 1] * 1.3333
    cs = half[0] * 1.3333
    te = _unit(pts[a - 2], pts[a - 1])
    ts = _unit(pts[1], pts[0])
    path.append(("M",) + left[0])
    _quad_chain(path, left)
    path.append(("C", left[a - 1][0] + te[0] * ce, left[a - 1][1] + te[1] * ce,
                 right[0][0] + te[0] * ce, right[0][1] + te[1] * ce, right[0][0], right[0][1]))
    _quad_chain(path, right)
    path.append(("C", right[a - 1][0] + ts[0] * cs, right[a - 1][1] + ts[1] * cs,
                 left[0][0] + ts[0] * cs, left[0][1] + ts[1] * cs, left[0][0], left[0][1]))
    path.append(("Z",))
    return path


# ---- one frame ----

def _blob(t, radius):
    q = math.floor(t / LOOP * 24) / 24  # steps like the app's ~125 ms blob updates
    pts = []
    for e in range(48):
        r = TAU * e / 48
        i = 1 + 0.018 * (math.sin(3 * r + TAU * 4 * q + SEED) + 0.6 * math.sin(5 * r - TAU * 6 * q))
        pts.append((radius * i * math.cos(r), radius * i * math.sin(r)))
    last, first = pts[-1], pts[0]
    path = [("M", (last[0] + first[0]) / 2, (last[1] + first[1]) / 2)]
    for k, pnt in enumerate(pts):
        nxt = pts[(k + 1) % len(pts)]
        path.append(("Q", pnt[0], pnt[1], (pnt[0] + nxt[0]) / 2, (pnt[1] + nxt[1]) / 2))
    path.append(("Z",))
    return path


def _strokes(t):
    """Ink outlines of the ring at time t: (behind the blob, in front of it)."""
    n = 200
    es = [i / n for i in range(n + 1)]
    boil = BOIL[int(math.floor(t / LOOP * 40)) % 4]  # the ink "boils" every ~84 ms
    edge = TAU * t / LOOP
    back, front = [], []
    run = [es[0]]
    for e in es[1:]:
        if orbit_behind(e, t) != orbit_behind(run[0], t):
            (back if orbit_behind(run[0], t) else front).append(run + [e])
            run = [e]
        else:
            run.append(e)
    (back if orbit_behind(run[0], t) else front).append(run)
    mk = lambda seg: brush([orbit_point(e, t) for e in seg], RING_WIDTH, SEED, boil, edge)
    return [mk(s) for s in back if len(s) > 1], [mk(s) for s in front if len(s) > 1]


def frame(t):
    """(ink behind the blob, blob outline, ink in front) at time t in seconds."""
    back, front = _strokes(t)
    return back, _blob(t, ORBIT_RADIUS), front


def trace(ctx, path):
    """Add a path from the ops above to a cairo context (quadratics become cubics)."""
    for op in path:
        kind = op[0]
        if kind == "M":
            ctx.move_to(op[1], op[2])
        elif kind == "L":
            ctx.line_to(op[1], op[2])
        elif kind == "Q":
            x0, y0 = ctx.get_current_point()
            qx, qy, x, y = op[1:]
            ctx.curve_to(x0 + 2 / 3 * (qx - x0), y0 + 2 / 3 * (qy - y0),
                         x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y), x, y)
        elif kind == "C":
            ctx.curve_to(*op[1:])
        elif kind == "Z":
            ctx.close_path()
        elif kind == "circle":
            ctx.new_sub_path()
            ctx.arc(op[1], op[2], op[3], 0, TAU)
            ctx.close_path()


def draw(ctx, t, shadow=False):
    """Draw the mascot at time t (seconds) in viewBox units on ctx (caller sets transform)."""
    back, blob, front = frame(t)
    layers = [(INK, back), (CLAY, [blob]), (INK, front)]
    for color, paths in layers:
        if shadow:
            ctx.set_source_rgba(0, 0, 0, 1)
        else:
            ctx.set_source_rgb(*color)
        for path in paths:
            trace(ctx, path)
            ctx.fill()


# ---- symbols: the ink line forms a glyph on the blob ----
# Each glyph is a list of strokes (centerlines in viewBox units, blob centered at (0, 0)).
# Over one loop the line writes the glyph on stroke by stroke, holds it while the ink
# boils, then pulls away from the first stroke to the last, like Duet changing poses.

def _arc(cx, cy, r, a0, a1, n=48):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def _seg(*pts, n=24):
    out = []
    for a, b in zip(pts, pts[1:]):
        for i in range(0 if not out else 1, n + 1):
            out.append((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n))
    return out


def _stadium(cx, cy, w, h, ang):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    r = h / 2
    pts = _arc(w / 2 - r, 0, r, -90, 90, 20) + _arc(-w / 2 + r, 0, r, 90, 270, 20)
    pts.append(pts[0])
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]


GLYPHS = {
    # strokes, dots (x, y, r) that appear once the last stroke is written
    "question": ([_arc(0, -5.5, 6.5, 195, 400) + _seg((2.2, 0.6), (0, 3.2), (0, 5.2), n=8)[1:]],
                 [(0, 11.2, 2.3)]),
    "plus": ([_seg((-10.5, 0), (10.5, 0)), _seg((0, -10.5), (0, 10.5))], []),
    "menu": ([_seg((-10, y), (10, y)) for y in (-7, 0, 7)], []),
    "forbid": ([_arc(0, 0, 10.5, -90, 280, 64), _seg((-7.4, 7.4), (7.4, -7.4))], []),
    "curve": ([_arc(-1.5, 3.5, 9, 180, 360) + _seg((7.5, 3.5), (7.5, 7.5), n=6)[1:],
               _seg((3, 3.5), (7.5, 9), (12, 3.5), n=12)], []),
    "chain": ([_stadium(-4, 4, 15, 8, -45), _stadium(4, -4, 15, 8, -45)], []),
    "w": ([_seg((-11.5, -7), (-5.7, 8), (0, -3.5), (5.7, 8), (11.5, -7), n=16)], []),
    "x": ([_seg((-8.5, -8.5), (8.5, 8.5)), _seg((-8.5, 8.5), (8.5, -8.5))], []),
}


def _length(pts):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def _slice(pts, lo, hi):
    """Points of the stroke between arc lengths lo and hi."""
    out, run = [], 0.0
    for a, b in zip(pts, pts[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        if d == 0:
            continue
        s0, s1 = run, run + d
        if s1 >= lo and s0 <= hi:
            t0 = max(0.0, (lo - s0) / d)
            t1 = min(1.0, (hi - s0) / d)
            p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
            if not out:
                out.append(p0)
            out.append(p1)
        run = s1
    return out


SYMBOL_WRITE = (0.0, 0.24)    # loop fraction while the glyph writes on
SYMBOL_RETRACT = (0.86, 0.97)  # loop fraction while it pulls away; then a moment of bare blob


def symbol_frame(kind, u):
    """(ink outlines, blob outline) for glyph `kind` at loop fraction u."""
    strokes, dots = GLYPHS[kind]
    lengths = [_length(s) for s in strokes]
    total = sum(lengths)
    w0, w1 = SYMBOL_WRITE
    r0, r1 = SYMBOL_RETRACT
    head = total * _write_ease((u - w0) / (w1 - w0))
    tail = total * _smooth((u - r0) / (r1 - r0))
    boil = BOIL[int(math.floor(u * 48)) % 4]
    edge = TAU * u
    ink, start = [], 0.0
    for i, (s, L) in enumerate(zip(strokes, lengths)):
        lo, hi = max(tail - start, 0.0), min(head - start, L)
        if hi - lo > 0.05:
            pts = _slice(s, lo, hi)
            if len(pts) > 1:
                ink.append(brush(pts, INK_WIDTH, SEED + i * 2.1, boil, edge))
        start += L
    if head >= total - 1e-6 and tail < total:
        for x, y, r in dots:
            ink.append([("circle", x, y, r)])
    return ink, _blob(u * LOOP, 18.0)


def draw_symbol(ctx, kind, u, shadow=False):
    ink, blob = symbol_frame(kind, u)
    for color, paths in ((CLAY, [blob]), (INK, ink)):
        if shadow:
            ctx.set_source_rgba(0, 0, 0, 1)
        else:
            ctx.set_source_rgb(*color)
        for path in paths:
            trace(ctx, path)
            ctx.fill()
