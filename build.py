#!/usr/bin/env python3
"""Build Claude Cursors, an animated Xcursor theme.

The pointer is the Claude spark logo, centered, with the click point at its hub. Each leg
stretches and sways on its own. Holding a window shortens the legs; the hub stays put.
Busy cursors show Claude Duet's mascot with an ink ring orbiting it, the help/copy/link/menu/not-allowed badges
are Duet's blob with the ink line forming the symbol, and the text caret and resize arrows
are drawn in Duet's ink. The pointing hand is the logo itself.

Usage: python3 build.py OUT_DIR [--inherits THEME] [--no-starpoint] [--preview PREVIEW_DIR]
  e.g. python3 build.py ~/.icons/claude-cursors
"""
import math
import os
import struct
import sys

import cairo

import duet
import ink_symbols
import spark_logo

THEME = "claude-cursors"
COLOR = (0xD9 / 255, 0x77 / 255, 0x57 / 255)  # Claude orange #D97757
SIZES = [12, 18, 24, 30, 36, 42, 48, 54, 60, 66, 72, 84, 96]  # same steps as Starpoint, plus 84/96
FRAMES = 48
DELAY_MS = 70  # 48 * 70ms = 3.36s loop

GRAB_SCALE = 0.65  # leg length past the hub while a window is held

# Motion: every leg jitters on its own, with its own speeds and phases, stretching and
# swaying independently. Frequencies are whole numbers so the loop is seamless.
STRETCH = 0.11    # main stretch amplitude
FLICKER = 0.05    # faster secondary stretch
SWAY_DEG = 4.5    # sideways sway
MAX_STRETCH = 1 + STRETCH * 1.3 + FLICKER  # longest a leg ever gets

# The spark's reach at full stretch, as a fraction of half the cursor size.
FILL = 0.94

# Badges and the busy mascot sit at the lower right; the spark shrinks toward its hub.
BADGE_SHRINK = 0.62
BADGE_POS = (0.765, 0.765, 0.215)  # badge blob center x, y and radius, per cursor size
BUSY_SHRINK = 0.62
BUSY_SCALE = 0.0098  # mascot viewBox unit in pixels, per pixel of cursor size
# The pointing hand: the spark unravels, its legs meet at the click point, and a solid
# teardrop grows out of that point with its tip on it. Xcursor animations always loop, so
# the last frame (the teardrop) is held for an hour.
MORPH_MS = 48                       # frame length while morphing (20 frames, about 1 s)
UNRAVEL, CONVERGE, GROW = 8, 3, 10  # frames in each part
HOLD_MS = 3_600_000
BEND_TO = math.radians(-135)        # the teardrop's tip direction (up-left); legs curve toward it
BEND = 0.8                          # how much of the way each leg curves toward it
BEND_MAX = math.radians(120)        # cap for legs pointing the opposite way
TEAR_RATIO = 1.8                    # tip-to-center distance / body radius (higher = sharper tip)
GROW_OVERSHOOT = 1.2                # how much the teardrop overshoots as it pops in


def _rand(i, salt):
    v = math.sin(i * 12.9898 + salt * 78.233) * 43758.5453
    return v - math.floor(v)


def leg_motion(i, t):
    """Return (length factor, sway in radians) for leg i at loop time t in [0, 1)."""
    tau = 2 * math.pi
    k1 = 2 + int(_rand(i, 1) * 3)   # 2..4 stretches per loop
    k2 = 5 + int(_rand(i, 2) * 3)   # 5..7 flickers per loop
    ks = 1 + int(_rand(i, 3) * 3)   # 1..3 sways per loop
    amp = STRETCH * (0.7 + 0.6 * _rand(i, 4))
    f = (1 + amp * math.sin(tau * (k1 * t + _rand(i, 5)))
         + FLICKER * math.sin(tau * (k2 * t + _rand(i, 6))))
    sway = math.radians(SWAY_DEG) * math.sin(tau * (ks * t + _rand(i, 7)))
    return f, sway


def hotspot(size):
    return (size // 2, size // 2)


def _center(size):
    """Pixel position of the hub: the middle of the hotspot pixel."""
    return size // 2 + 0.5, size // 2 + 0.5


def _unit(size):
    """Pixels per logo unit so the fully stretched spark fills FILL of the half-size."""
    reach = spark_logo.HUB_EDGE + (spark_logo.REACH - spark_logo.HUB_EDGE) * MAX_STRETCH
    return (size / 2 - 0.5) * FILL / reach


def blur(surf, r):
    from PIL import Image, ImageFilter
    w, h = surf.get_width(), surf.get_height()
    im = Image.frombuffer("RGBA", (w, h), bytes(surf.get_data()), "raw", "BGRA", 0, 1)
    im = im.filter(ImageFilter.GaussianBlur(r))
    data = bytearray(im.tobytes("raw", "BGRA"))
    return cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h)


def _to_pil(surf, size):
    from PIL import Image
    return Image.frombuffer("RGBA", (size, size), bytes(surf.get_data()), "raw", "BGRa", 0, 1).copy()


def _paint(size, draw):
    """Render draw(ctx, shadow) with the soft drop shadow every cursor here uses."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    shadow = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx, sctx = cairo.Context(surf), cairo.Context(shadow)
    for c in (ctx, sctx):
        c.set_antialias(cairo.ANTIALIAS_BEST)
    sctx.translate(0, 0.02 * size)
    draw(sctx, True)
    ctx.set_source_surface(blur(shadow, max(1, size // 28)), 0, 0)
    ctx.paint_with_alpha(0.32)
    draw(ctx, False)
    surf.flush()
    return _to_pil(surf, size)


# ---- the spark ----

def spark_image(size, t, grab=False, shrink=1.0, still=False, breathe=1.0):
    """Spark centered on the hotspot. t in [0, 1) drives the legs unless `still`."""
    n = spark_logo.N_LEGS
    if still:
        stretch, sway = [1.0] * n, [0.0] * n
    else:
        motion = [leg_motion(i, t) for i in range(n)]
        stretch, sway = [m[0] for m in motion], [m[1] for m in motion]
    pts = spark_logo.outline(stretch, sway, GRAB_SCALE if grab else 1.0)
    cx, cy = _center(size)
    k = _unit(size) * shrink * breathe

    def draw(ctx, shadow):
        ctx.new_path()
        ctx.move_to(cx + pts[0][0] * k, cy + pts[0][1] * k)
        for x, y in pts[1:]:
            ctx.line_to(cx + x * k, cy + y * k)
        ctx.close_path()
        if shadow:
            ctx.set_source_rgba(0, 0, 0, 1)
        else:
            ctx.set_source_rgb(*COLOR)
        ctx.fill()

    return _paint(size, draw)


def _ease_in(t):
    return t * t * t


def _ease_out_back(t, s=1.7):
    t -= 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


def _hull(pts):
    pts = sorted(set(pts))
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def teardrop_image(size, grow):
    """Solid orange teardrop, tip on the click point, body to the lower right; `grow`
    scales it about the tip (0 = a point, 1 = full size)."""
    tx, ty = _center(size)
    peak = max(_ease_out_back(i / 200, GROW_OVERSHOOT) for i in range(201))
    room = size / 2 - 0.5 - max(1.5, size / 24)            # margin for the shadow
    R = room / (TEAR_RATIO / math.sqrt(2) + 1) / peak      # fits even at its biggest
    d = TEAR_RATIO * R
    ux = uy = 1 / math.sqrt(2)                             # toward the lower right
    rt = 0.14 * R                                          # rounded tip
    off = rt / (R / d)                                     # keeps the tip's outer edge on the point
    circles = [(tx + ux * d, ty + uy * d, R), (tx + ux * off, ty + uy * off, rt)]
    pts = [(cx + r * math.cos(a * math.pi / 64), cy + r * math.sin(a * math.pi / 64))
           for cx, cy, r in circles for a in range(128)]
    pts = [(tx + (x - tx) * grow, ty + (y - ty) * grow) for x, y in _hull(pts)]

    def draw(ctx, shadow):
        if grow <= 0.01:
            return
        ctx.new_path()
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.close_path()
        if shadow:
            ctx.set_source_rgba(0, 0, 0, 1)
        else:
            ctx.set_source_rgb(*COLOR)
        ctx.fill()

    return _paint(size, draw)


def hover_frames(size):
    """[(image, delay ms)] for the pointing hand: unravel, converge, grow, hold."""
    n = spark_logo.N_LEGS
    out = []
    def bends(amount):
        out = []
        for a in spark_logo.LEG_ANGLE:
            diff = (BEND_TO - a + math.pi) % (2 * math.pi) - math.pi
            out.append(max(-BEND_MAX, min(BEND_MAX, diff)) * BEND * amount)
        return out

    for f in range(UNRAVEL):  # each leg curves toward the tip direction and pulls into the hub
        p = (f + 1) / UNRAVEL
        curve = 1 - (1 - p) ** 2
        pts = spark_logo.outline([1.0] * n, bends(curve), 1 - _ease_in(p) * 0.999)
        out.append((_shape_image(size, pts, 1.0), MORPH_MS))
    for f in range(CONVERGE):  # the hub closes into the click point
        p = (f + 1) / (CONVERGE + 1)
        pts = spark_logo.outline([1.0] * n, bends(1.0), 0.001)
        out.append((_shape_image(size, pts, 1 - p * 0.92), MORPH_MS))
    for f in range(GROW):  # the teardrop grows out of the point
        out.append((teardrop_image(size, _ease_out_back((f + 1) / GROW, GROW_OVERSHOOT)), MORPH_MS))
    out[-1] = (out[-1][0], HOLD_MS)
    return out


def _shape_image(size, pts, k_mul):
    cx, cy = _center(size)
    k = _unit(size) * k_mul

    def draw(ctx, shadow):
        ctx.new_path()
        ctx.move_to(cx + pts[0][0] * k, cy + pts[0][1] * k)
        for x, y in pts[1:]:
            ctx.line_to(cx + x * k, cy + y * k)
        ctx.close_path()
        if shadow:
            ctx.set_source_rgba(0, 0, 0, 1)
        else:
            ctx.set_source_rgb(*COLOR)
        ctx.fill()

    return _paint(size, draw)


# ---- Duet pieces ----

def _duet(size, scale, ox, oy, draw_fn):
    def draw(ctx, shadow):
        ctx.save()
        ctx.translate(ox, oy)
        ctx.scale(scale, scale)
        draw_fn(ctx, shadow)
        ctx.restore()
    return _paint(size, draw)


def symbol_badge(size, kind, u, cx, cy, rad):
    """Duet blob (radius `rad` px) at cx, cy with the ink forming `kind`."""
    k = rad / 18.0
    return _duet(size, k, cx, cy, lambda ctx, sh: duet.draw_symbol(ctx, kind, u, shadow=sh))


def busy_image(size, f):
    """Frame f: smaller spark with the orbiting Duet mascot at the lower right."""
    im = spark_image(size, (f % FRAMES) / FRAMES, shrink=BUSY_SHRINK)
    k = BUSY_SCALE * size
    x0, y0, x1, y1 = duet.BOUNDS
    ox, oy = size - 0.5 - x1 * k, size - 0.5 - y1 * k
    secs = f * DELAY_MS / 1000
    im.alpha_composite(_duet(size, k, ox, oy, lambda ctx, sh: duet.draw(ctx, secs, shadow=sh)))
    return im


def wait_image(size, f):
    """Frame f: the Duet mascot alone, filling the cursor."""
    x0, y0, x1, y1 = duet.BOUNDS
    k = (size - 1) / (x1 - x0)
    ox, oy = size / 2 - (x0 + x1) / 2 * k, size / 2 - (y0 + y1) / 2 * k
    secs = f * DELAY_MS / 1000
    return _duet(size, k, ox, oy, lambda ctx, sh: duet.draw(ctx, secs, shadow=sh))


def badged_image(size, f, kind):
    """Frame f: smaller spark with a Duet symbol badge at the lower right."""
    u = f / FRAMES
    im = spark_image(size, u, shrink=BADGE_SHRINK)
    bx, by, br = (v * size for v in BADGE_POS)
    im.alpha_composite(symbol_badge(size, kind, u, bx, by, br))
    return im


def round_image(size, f, kind):
    """Frame f: one large Duet symbol filling the cursor."""
    cx, cy = _center(size)
    return symbol_badge(size, kind, f / FRAMES, cx, cy, size * 0.42)


def ink_image(size, u, name):
    return _to_pil(ink_symbols.render(size, u, name, blur), size)


# ---- Starpoint (optional: the drag-and-drop hands reuse its hand drawings) ----

STARPOINT = os.path.expanduser("~/.icons/starpoint_cursors/cursors")
STARPOINT_SRC = os.path.expanduser("~/.local/share/starpoint-cursors")
VOLANTES = os.path.expanduser("~/.icons/volantes_light_cursors/cursors")


def read_xcursor(path):
    """Return {nominal size: [(PIL RGBA image, delay ms), ...]} from an Xcursor file."""
    from PIL import Image
    d = open(path, "rb").read()
    n = struct.unpack("<I", d[12:16])[0]
    out = {}
    for i in range(n):
        typ, nominal, pos = struct.unpack("<III", d[16 + i * 12:28 + i * 12])
        if typ != 0xFFFD0002:
            continue
        _, _, _, _, w, h, xh, yh, delay = struct.unpack("<9I", d[pos:pos + 36])
        im = Image.frombytes("RGBA", (w, h), d[pos + 36:pos + 36 + w * h * 4], "raw", "BGRa")
        out.setdefault(nominal, []).append((im, delay, xh, yh))
    return out


def hand_frames(name, kind):
    """Volantes' drag-and-drop hand (from Starpoint) with a Duet symbol in its badge spot."""
    from PIL import Image
    if STARPOINT_SRC not in sys.path:
        sys.path.insert(0, STARPOINT_SRC)
    import badges as sp_badges
    # Where Volantes puts the badge on this hand, measured on its largest original.
    vol = read_xcursor(os.path.join(VOLANTES, name))
    vs = max(vol)
    vcx, vcy, vrad = sp_badges.badge_circle(vol[vs][0][0])
    sp = read_xcursor(os.path.join(STARPOINT, name))

    def frames(size):
        if size in sp:
            base, _, hx, hy = sp[size][0]
        else:
            big = max(sp)
            base, _, hx, hy = sp[big][0]
            base = base.resize((size, size), Image.LANCZOS)
            hx, hy = round(hx * size / big), round(hy * size / big)
        r = size / vs
        cx, cy, rad = vcx * r, vcy * r, vrad * r
        hand = sp_badges.erase_circle(base, (cx, cy, rad * 1.2))  # Starpoint's hexagon is a bit larger
        out = []
        for f in range(FRAMES):
            im = hand.copy()
            im.alpha_composite(symbol_badge(size, kind, f / FRAMES, cx, cy, rad))
            out.append(im)
        return out, (hx, hy)
    return frames


# Other names apps use for the same cursor (taken from Volantes, which Starpoint follows).
ALIASES = {
    'pointer': ['9d800788f1b08800ae810202380a0822', 'e29285e634086352946a0e7090d73106', 'hand', 'hand1', 'hand2', 'pointing_hand'],
    'help': ['5c6cd98b3f3ebcb1f9c7f1c204630408', 'd9ce0ab605698f320427677b458ad60b', 'left_ptr_help', 'question_arrow', 'whats_this'],
    'copy': ['1081e37283d90000800003c07f3ef6bf', '6407b0e94181790501fd1e167b474872', 'b66166c04f8c3109214a4fbd64a50fc8', 'dnd-copy'],
    'alias': ['3085a0e285430894940527032f8b26df', '640fb0e74195791501fd1ed57b41487f', 'a2a266d0498c3104214a47bd64ab0fc8', 'link'],
    'no-drop': ['forbidden'],
    'not-allowed': ['03b6e0fcb3499374a867c041f52298f0', 'circle', 'crossed_circle'],
    'x-cursor': ['X_cursor'],
    'text': ['ibeam', 'xterm'],
    'size_hor': ['028006030e0e7ebffc7f7070c0600140', '14fef782d02440884392942c11205230', 'e-resize', 'ew-resize', 'h_double_arrow', 'sb_h_double_arrow', 'w-resize'],
    'size_ver': ['00008160000006810000408080010102', '2870a09082c103050810ffdffffe0204', 'double_arrow', 'n-resize', 'ns-resize', 's-resize', 'sb_v_double_arrow', 'v_double_arrow'],
    'size_fdiag': ['nw-resize', 'nwse-resize', 'se-resize'],
    'size_bdiag': ['bd_double_arrow', 'c7088f0f3e6c8088236ef8e1e3e70000', 'fcf1c3c7cd4491d801f1e1c78f100000', 'fd_double_arrow', 'ne-resize', 'nesw-resize', 'sw-resize'],
    'col-resize': ['split_h'],
    'row-resize': ['split_v'],
}


def aliases(name):
    return ALIASES.get(name, [])


# ---- writing ----

def write_frames(path, frames_for_size, delay=DELAY_MS):
    """frames_for_size(size) -> ([PIL images], (hx, hy)); every frame lasts `delay` ms."""
    images = []
    for size in SIZES:
        ims, (hx, hy) = frames_for_size(size)
        for im in ims:
            im, dl = im if isinstance(im, tuple) else (im, delay)  # (image, delay) sets its own
            images.append((size, im.size[0], im.size[1], hx, hy, dl, im.tobytes("raw", "BGRa")))
    ntoc = len(images)
    header = struct.pack("<4sIII", b"Xcur", 16, 0x10000, ntoc)
    pos = 16 + ntoc * 12
    toc, chunks = [], []
    for nominal, w, h, hx, hy, dl, px in images:
        toc.append(struct.pack("<III", 0xFFFD0002, nominal, pos))
        chunk = struct.pack("<9I", 36, 0xFFFD0002, nominal, 1, w, h, hx, hy, dl) + px
        chunks.append(chunk)
        pos += len(chunk)
    with open(path, "wb") as fh:
        fh.write(header + b"".join(toc) + b"".join(chunks))


def _link_all(cur, primary, names):
    for n in names:
        if n == primary:
            continue
        link = os.path.join(cur, n)
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(primary, link)


POINTER_NAMES = ["left_ptr", "default", "arrow", "top_left_arrow"]
GRAB_NAMES = [
    "grabbing", "closedhand", "fleur", "size_all", "all-scroll", "move", "dnd-move",
    "4498f0e0c1937ffe01fd06f973665830", "9081237383d90e509aa00f00170e968f",
    "fcf21c00b30f7e3f83fe0dfd12e71cff",
]
BUSY_NAMES = ["progress", "left_ptr_watch", "half-busy", "00000000000000020006000e7e9ffc3f",
              "08e8e1c95fe2fc01f976f1e063a24ccd", "3ecb610c1bf2410f44200f48c40d3599"]
WAIT_NAMES = ["wait", "watch"]
BADGED = {"help": "question", "copy": "plus", "alias": "curve",
          "context-menu": "menu", "no-drop": "forbid"}
HANDS = {"dnd-ask": "question", "dnd-link": "chain", "dnd-no-drop": "forbid"}
ROUND = {"not-allowed": "forbid", "wayland-cursor": "w", "x-cursor": "x"}
# One trip of the busy animation is duet.LOOP seconds (3.36 s = 48 frames at 70 ms, the spark's loop).
BUSY_FRAMES = round(duet.LOOP * 1000 / DELAY_MS)


def have_starpoint():
    return all(os.path.isdir(p) for p in (STARPOINT, STARPOINT_SRC, VOLANTES))


def build(out_dir, inherits=None, use_starpoint=True):
    """Write the theme to out_dir. Cursors it doesn't draw come from `inherits`
    (Starpoint if installed and allowed, otherwise Breeze)."""
    use_starpoint = use_starpoint and have_starpoint()
    if inherits is None:
        inherits = "starpoint_cursors" if use_starpoint else "breeze_cursors"
    cur = os.path.join(out_dir, "cursors")
    os.makedirs(cur, exist_ok=True)
    every = lambda fn, n=FRAMES: (lambda s: ([fn(s, f) for f in range(n)], hotspot(s)))

    write_frames(os.path.join(cur, "left_ptr"), every(lambda s, f: spark_image(s, f / FRAMES)))
    _link_all(cur, "left_ptr", POINTER_NAMES)
    write_frames(os.path.join(cur, "grabbing"), every(lambda s, f: spark_image(s, f / FRAMES, grab=True)))
    _link_all(cur, "grabbing", GRAB_NAMES)

    write_frames(os.path.join(cur, "pointer"), lambda s: (hover_frames(s), hotspot(s)))
    _link_all(cur, "pointer", aliases("pointer"))

    write_frames(os.path.join(cur, "progress"), every(busy_image, BUSY_FRAMES))
    _link_all(cur, "progress", BUSY_NAMES)
    write_frames(os.path.join(cur, "wait"), every(wait_image, BUSY_FRAMES))
    _link_all(cur, "wait", WAIT_NAMES)

    for name, kind in BADGED.items():
        write_frames(os.path.join(cur, name), every(lambda s, f, k=kind: badged_image(s, f, k)))
        _link_all(cur, name, aliases(name))
    for name, kind in ROUND.items():
        write_frames(os.path.join(cur, name), every(lambda s, f, k=kind: round_image(s, f, k)))
        _link_all(cur, name, aliases(name))
    if use_starpoint:  # otherwise the hands come from the inherited theme
        for name, kind in HANDS.items():
            write_frames(os.path.join(cur, name), hand_frames(name, kind))
            _link_all(cur, name, aliases(name))

    for name in ink_symbols.SYMBOLS:
        # The ink wobble steps every other frame, so half the frames at double length look the same.
        n_ink = ink_symbols.BOIL_STEPS
        write_frames(os.path.join(cur, name),
                     every(lambda s, f, n=name: ink_image(s, f / n_ink, n), n_ink),
                     delay=DELAY_MS * FRAMES // n_ink)
        _link_all(cur, name, aliases(name))

    with open(os.path.join(out_dir, "index.theme"), "w") as fh:
        fh.write("[Icon Theme]\nName=Claude Cursors\nComment=Animated cursors built from the Claude logo\n"
                 f"Inherits={inherits}\n")


def preview(out_dir, size=96, scale=3):
    from PIL import Image
    os.makedirs(out_dir, exist_ok=True)
    for name, fn in (("pointer", lambda f: spark_image(size, f / FRAMES)),
                     ("grab", lambda f: spark_image(size, f / FRAMES, grab=True))):
        frames = []
        for f in range(FRAMES):
            bg = Image.new("RGBA", (size, size), (238, 238, 238, 255))
            bg.alpha_composite(fn(f))
            frames.append(bg.resize((size * scale, size * scale), Image.LANCZOS).convert("RGB"))
        frames[0].save(os.path.join(out_dir, f"{name}.gif"), save_all=True,
                       append_images=frames[1:], duration=DELAY_MS, loop=0)
        frames[0].save(os.path.join(out_dir, f"{name}.png"))


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--preview" in args:
        i = args.index("--preview")
        preview(args[i + 1])
        del args[i:i + 2]
    inherits = None
    if "--inherits" in args:
        i = args.index("--inherits")
        inherits = args[i + 1]
        del args[i:i + 2]
    use_starpoint = "--no-starpoint" not in args
    args = [a for a in args if a != "--no-starpoint"]
    if args:
        build(args[0], inherits, use_starpoint)
