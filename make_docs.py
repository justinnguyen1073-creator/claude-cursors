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

# Showcase: one cursor stepping through its main shapes (see showcase.py), for the README
# and the first store gallery image.
import showcase

C, W = 240, 280
show = []
for im, ms in showcase.frames(C):
    f = Image.new('RGBA', (W, W), BG)
    f.alpha_composite(im, ((W - C) // 2, (W - C) // 2))
    show.append((f, ms))
save_gif('docs/showcase.gif', [f for f, _ in show], [ms for _, ms in show])
