"""Render the README GIFs in docs/ with one shared palette so every viewer shows the same colors.

Usage: python3 make_docs.py
"""
import sys
sys.path.insert(0, '.')
import build, ink_symbols
from PIL import Image

BG = (240, 238, 232, 255)

def save_gif(path, frames, delay, scale=1):
    rgb = []
    for row in frames:
        if scale != 1:
            row = row.resize((row.width * scale, row.height * scale), Image.LANCZOS)
        rgb.append(row.convert('RGB'))
    # One palette for the whole animation, built from a strip of sampled frames.
    sample = Image.new('RGB', (rgb[0].width, rgb[0].height * min(8, len(rgb))))
    for i in range(min(8, len(rgb))):
        sample.paste(rgb[i * len(rgb) // min(8, len(rgb))], (0, i * rgb[0].height))
    pal = sample.quantize(colors=96, method=Image.Quantize.MEDIANCUT)
    out = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in rgb]
    out[0].save(path, save_all=True, append_images=out[1:], duration=delay, loop=0,
                optimize=False, disposal=1)

def strip(ims, S, gap=0):
    row = Image.new('RGBA', (S * len(ims) + gap * (len(ims) - 1), S), BG)
    for k, im in enumerate(ims):
        row.alpha_composite(im, (k * (S + gap), 0))
    return row

S = 96
save_gif('docs/pointer.gif', [strip([build.spark_image(S, f / 48), build.spark_image(S, f / 48, grab=True)], S) for f in range(48)], 70, scale=2)
# Hover: the spark for a moment, the morph at real speed, then the teardrop.
spark = [build.spark_image(S, f / 48) for f in range(0, 48, 2)]
morph = [im for im, _ in build.hover_frames(S)]
save_gif('docs/hover.gif', [strip([im], S) for im in spark + morph + [morph[-1]] * 20],
         [70] * len(spark) + [build.MORPH_MS] * len(morph) + [70] * 20, scale=2)
save_gif('docs/busy.gif', [strip([build.busy_image(S, f), build.wait_image(S, f)], S, gap=24) for f in range(build.BUSY_FRAMES)], 70, scale=2)
kinds = list(build.BADGED.values())
save_gif('docs/symbols.gif', [strip([build.badged_image(S, f, k) for k in kinds], S, gap=24) for f in range(48)], 70)
names = list(ink_symbols.SYMBOLS)
save_gif('docs/ink.gif', [strip([build.ink_image(S, f / 24, n) for n in names], S) for f in range(24)], 140)

# Showcase: one cursor stepping through its main shapes, labeled, for the first gallery image.
# Pointer -> link hover (the legs fold into the teardrop) -> busy -> help -> back to the pointer.
# The cursor canvas stays put, so the click point never moves, just like on screen.
import glob
from PIL import ImageDraw, ImageFont

def showcase(path, C=200, W=340):
    fonts = glob.glob('/usr/share/fonts/**/NotoSans-Regular.ttf', recursive=True) + \
        glob.glob('/usr/share/fonts/**/NotoSans*.ttf', recursive=True)
    font = ImageFont.truetype(fonts[0], 26) if fonts else ImageFont.load_default()
    frames, delays = [], []

    def add(im, label, ms):
        f = Image.new('RGBA', (W, W), BG)
        f.alpha_composite(im, ((W - C) // 2, 10))
        d = ImageDraw.Draw(f)
        tw = d.textlength(label, font=font)
        d.text(((W - tw) / 2, W - 52), label, fill=(60, 58, 52), font=font)
        frames.append(f)
        delays.append(ms)

    morph = [im for im, _ in build.hover_frames(C)]
    for k in range(0, 48, 2):
        add(build.spark_image(C, k / 48), 'Pointer', 70)
    for im in morph:
        add(im, 'Link hover', 60)
    add(morph[-1], 'Link hover', 700)
    for k in range(30):
        add(build.busy_image(C, k), 'Busy', 70)
    for k in range(38):
        add(build.badged_image(C, k, 'question'), 'Help', 70)
    for im in reversed(morph[:-1]):
        add(im, 'Pointer', 60)
    for k in range(0, 12, 2):
        add(build.spark_image(C, k / 48), 'Pointer', 70)
    save_gif(path, frames, delays)

showcase('docs/showcase.gif')
