"""The README / store showcase: one cursor stepping through its main shapes.

Pointer (the spark) -> link hover (the legs fold into the teardrop) -> busy (Duet's ink ring
grows out from behind the teardrop and circles it) -> help (the same ink line bends into
the question mark) -> the symbol pulls away and the teardrop unfolds back into the spark.
The cursor's click point stays put the whole time, as on screen.
"""
import math

from PIL import Image

import build
import duet

N = 160  # points along an ink line while it moves


def _resample(pts, n=N):
    seg = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(seg) or 1
    out, j, run = [], 0, 0.0
    for i in range(n):
        target = total * i / (n - 1)
        while j < len(seg) - 1 and run + seg[j] < target:
            run += seg[j]
            j += 1
        t = (target - run) / seg[j] if seg[j] else 0
        a, b = pts[j], pts[j + 1]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _ring_line(size, tip, t, lo=0.0, hi=1.0):
    """The busy ring's centerline at time t (px), from lo to hi along the drawn arc, with a
    flag per point for whether it is behind the teardrop."""
    cx, cy, k = build.busy_ring_place(size, tip)
    es = [lo + (hi - lo) * i / (N - 1) for i in range(N)]
    pts = [(cx + x * k, cy + y * k) for x, y in (duet.orbit_point(e, t) for e in es)]
    return pts, [duet.orbit_behind(e, t) for e in es], duet.RING_WIDTH * k


def _runs(pts, behind):
    """Split a line into runs that are all behind or all in front."""
    out, start = [], 0
    for i in range(1, len(pts) + 1):
        if i == len(pts) or behind[i] != behind[start]:
            out.append((behind[start], pts[max(0, start - 1):i]))
            start = i
    return [(b, r) for b, r in out if len(r) > 1]


def _frame(size, tip, canvas, t, lines, dots=()):
    """The teardrop with ink lines [(pts px, width px, behind)] and dots [(x, y, r)] in front."""
    tear = build.teardrop_points(size, tip=tip)
    boil = duet.BOIL[int(math.floor(t / duet.LOOP * 40)) % 4]
    edge = duet.TAU * t / duet.LOOP
    paths = [(behind, duet.brush(pts, w, duet.SEED, boil, edge)) for pts, w, behind in lines if len(pts) > 1]

    def draw(ctx, shadow):
        dark = (0, 0, 0, 1) if shadow else duet.INK + (1,)

        def ink(want_behind):
            ctx.set_source_rgba(*dark)
            for behind, path in paths:
                if behind == want_behind:
                    duet.trace(ctx, path)
                    ctx.fill()

        ink(True)
        ctx.new_path()
        ctx.move_to(*tear[0])
        for q in tear[1:]:
            ctx.line_to(*q)
        ctx.close_path()
        ctx.set_source_rgba(0, 0, 0, 1) if shadow else ctx.set_source_rgb(*build.COLOR)
        ctx.fill()
        ink(False)
        for x, y, r in dots:
            ctx.new_path()
            ctx.arc(x, y, r, 0, 2 * math.pi)
            ctx.set_source_rgba(*dark)
            ctx.fill()

    return build._paint(size, draw, canvas)


def _inside(poly, x, y):
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def _edge_dist(poly, x, y):
    best = float('inf')
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(x - x1 - t * dx, y - y1 - t * dy))
    return best


def _hidden_start(size, tip):
    """(busy frame, point 0..1 along the ring) where the ring has a point behind the
    teardrop and inside its outline, as deep inside as possible. The ring grows from there,
    so nothing shows until it comes out from behind."""
    tear = build.teardrop_points(size, tip=tip)
    cx, cy, k = build.busy_ring_place(size, tip)
    best = (0, 0.5, -1.0)
    for f in range(build.BUSY_FRAMES):
        t = f * build.DELAY_MS / 1000
        for i in range(201):
            e = i / 200
            if not duet.orbit_behind(e, t):
                continue
            x, y = duet.orbit_point(e, t)
            x, y = cx + x * k, cy + y * k
            if _inside(tear, x, y):
                d = _edge_dist(tear, x, y)
                if d > best[2]:
                    best = (f, e, d)
    return best[0], best[1]


def _smooth(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


def frames(C, pad=20):
    """[(image, ms)] for the whole showcase loop for a C px cursor, on a canvas `pad` px
    bigger on every side (the busy ring reaches past the cursor's own canvas). Every frame
    puts the click point at the same spot, as on screen."""
    out = []
    W = C + 2 * pad
    cx, cy = build._center(C)
    tip = (cx + pad, cy + pad)   # the click point on the showcase canvas

    def place(im, hub):
        """A C px cursor image whose click point is `hub`, moved onto the showcase canvas."""
        canvas = Image.new('RGBA', (W, W), (0, 0, 0, 0))
        canvas.alpha_composite(im, (round(tip[0] - hub[0]), round(tip[1] - hub[1])))
        return canvas

    ms = build.DELAY_MS
    tear_hub = build.tear_tip(C)
    morph = [place(im, tear_hub) for im, _ in build.hover_frames(C)]
    spark = lambda k: place(build.spark_image(C, k / build.FRAMES), build._center(C))

    # pointer, then the legs fold into the teardrop
    out += [(spark(k), ms) for k in range(0, 48, 2)]
    out += [(im, 60) for im in morph] + [(morph[-1], 560)]

    # busy: the ring grows out from behind the teardrop (its orbit held still while it
    # grows), then the busy animation carries on from that same frame
    grow = 12
    f0, deep = _hidden_start(C, tip)
    t0 = f0 * ms / 1000
    for f in range(grow):
        p = _smooth((f + 1) / grow)
        lo, hi = deep * (1 - p), deep + (1 - deep) * p
        pts, behind, w = _ring_line(C, tip, t0, lo, hi)
        out.append((_frame(C, tip, W, t0, [(r, w, b) for b, r in _runs(pts, behind)]), ms))
    busy_end = f0 + 22
    out += [(build.busy_image(C, f % build.BUSY_FRAMES, tip, W), ms) for f in range(f0, busy_end)]

    # help: the same ink line bends from the ring into the question mark
    t = busy_end * ms / 1000
    ring, behind, w_ring = _ring_line(C, tip, t)
    gx, gy, gs = build.glyph_place(C)
    gx, gy = gx + tip[0] - tear_hub[0], gy + tip[1] - tear_hub[1]
    (stroke,), dots = duet.GLYPHS["question"]
    q = _resample([(gx + x * gs, gy + y * gs) for x, y in stroke])
    ring = _resample(ring)
    flip = sum(math.dist(a, b) for a, b in zip(ring, q[::-1])) < sum(math.dist(a, b) for a, b in zip(ring, q))
    if flip:
        q = q[::-1]
    w_q = duet.INK_WIDTH * gs
    steps = 12
    for f in range(steps):
        p = _smooth((f + 1) / steps)
        pts = [(a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p) for a, b in zip(ring, q)]
        flags = [bb and p < 0.5 for bb in behind]  # the line comes all the way to the front
        dot = [(gx + x * gs, gy + y * gs, r * gs * _smooth((p - 0.75) / 0.25)) for x, y, r in dots] if p > 0.75 else []
        out.append((_frame(C, tip, W, t + f * ms / 1000, [(r, w_ring + (w_q - w_ring) * p, b) for b, r in _runs(pts, flags)], dot), 55))

    # hold the question mark, let the ink pull away, and unfold back into the spark
    write_done = math.ceil(duet.SYMBOL_WRITE[1] * build.FRAMES)
    out += [(place(build.badged_image(C, f, "question"), tear_hub), ms) for f in range(write_done, build.FRAMES)]
    out += [(im, 60) for im in reversed(morph[:-1])]
    out += [(spark(k), ms) for k in range(0, 12, 2)]
    return out
