"""The Claude spark logo as a polygon whose legs can move one at a time.

`claude-spark.path` is the spark from the Claude desktop app (24 x 24 viewBox).
Each leg is the run of outline points that reach past the hub. A leg stretches by scaling
its points' distance beyond the hub, and sways by rotating them, more toward the tip.
At rest (every leg factor 1, no sway) the outline is the logo exactly.
"""
import math
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))


def _parse(d):
    """Flatten an SVG path made of M/L/l/h/v/c/Z into one list of points."""
    toks = re.findall(r"[A-Za-z]|-?(?:\d+\.?\d*|\.\d+)", d)
    pts, i, cmd = [], 0, None
    x = y = 0.0

    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v

    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]; i += 1
            if cmd in "Zz":
                continue
        if cmd == "M":
            x, y = num(), num(); pts.append((x, y)); cmd = "L"
        elif cmd == "L":
            x, y = num(), num(); pts.append((x, y))
        elif cmd == "l":
            x, y = x + num(), y + num(); pts.append((x, y))
        elif cmd == "h":
            x += num(); pts.append((x, y))
        elif cmd == "v":
            y += num(); pts.append((x, y))
        elif cmd == "c":
            x1, y1, x2, y2, dx, dy = (num() for _ in range(6))
            p0, p1, p2, p3 = (x, y), (x + x1, y + y1), (x + x2, y + y2), (x + dx, y + dy)
            for k in range(1, 9):
                t = k / 8
                pts.append(tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t * t * c + t ** 3 * e
                                 for a, b, c, e in zip(p0, p1, p2, p3)))
            x, y = p3
        else:
            raise ValueError(f"unsupported path command {cmd}")
    if pts[0] == pts[-1]:
        pts.pop()
    return pts


def _inside(pts, x, y):
    c = False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def _seg_dist(px, py, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(px - a[0] - t * dx, py - a[1] - t * dy)


def _hub(pts):
    """Center and radius of the biggest circle inside the outline: the spark's hub."""
    best = (0.0, 12.0, 12.0)
    for gx in range(80, 161):
        for gy in range(80, 161):
            x, y = gx / 10, gy / 10
            if not _inside(pts, x, y):
                continue
            d = min(_seg_dist(x, y, a, b) for a, b in zip(pts, pts[1:] + pts[:1]))
            if d > best[0]:
                best = (d, x, y)
    return best[1], best[2], best[0]


OUTLINE = _parse(open(os.path.join(_HERE, "claude-spark.path")).read())
CX, CY, HUB = _hub(OUTLINE)
HUB_EDGE = HUB * 1.25  # points closer than this belong to the hub and never move
_POLAR = [(math.hypot(x - CX, y - CY), math.atan2(y - CY, x - CX)) for x, y in OUTLINE]
REACH = max(r for r, _ in _POLAR)  # longest leg, in logo units


def _legs():
    """Leg index for each outline point, legs numbered around the spark.

    A leg is a run of points reaching past SPLIT; the dips between runs are the valleys.
    Each valley point joins the nearest leg, and only its distance past the hub moves.
    """
    split = 0.45 * REACH
    far = [r > split for r, _ in _POLAR]
    n = len(_POLAR)
    start = far.index(False)  # begin the scan inside a valley so runs don't wrap
    run_of, leg, prev = [None] * n, -1, False
    for k in range(n):
        j = (start + k) % n
        if far[j]:
            if not prev:
                leg += 1
            run_of[j] = leg
        prev = far[j]
    ids = list(run_of)
    for j in range(n):
        if ids[j] is None:
            for d in range(1, n):
                a, b = run_of[(j - d) % n], run_of[(j + d) % n]
                if a is not None or b is not None:
                    ids[j] = a if a is not None else b
                    break
    return ids, leg + 1


LEG_OF, N_LEGS = _legs()


def outline(stretch, sway, scale=1.0):
    """Logo outline with per-leg `stretch` factors and `sway` angles (radians), centered
    on the hub at (0, 0); `scale` multiplies every leg's reach past the hub."""
    pts = []
    for (r, a), leg in zip(_POLAR, LEG_OF):
        if leg is not None and r > HUB_EDGE:
            k = (r - HUB_EDGE) / (REACH - HUB_EDGE)
            r = HUB_EDGE + (r - HUB_EDGE) * stretch[leg] * scale
            a += sway[leg] * k
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts
