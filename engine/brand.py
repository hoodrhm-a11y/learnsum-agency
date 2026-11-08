"""LearnSum visual identity: fonts, colours, Pip the mascot and shared drawing helpers."""
import os
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "assets", "fonts")
BLACK = os.path.join(FONTS, "Inter-Black.otf")
XBOLD = os.path.join(FONTS, "Inter-ExtraBold.otf")
BOLD = os.path.join(FONTS, "Inter-Bold.otf")
SEMI = os.path.join(FONTS, "Inter-SemiBold.otf")
MED = os.path.join(FONTS, "Inter-Medium.otf")
REG = os.path.join(FONTS, "Inter-Regular.otf")
DISPLAY = os.path.join(FONTS, "InterDisplay-Black.otf")

# LearnSum palette (matches learnsum.ca): deep navy, Pip green and sunshine gold.
INK = (11, 21, 51)        # darkest navy (text on light slides, bottom of gradients)
GREEN = (19, 32, 74)      # navy (top of gradients, titles on light slides); name kept for the shared layouts
JADE = (22, 168, 100)     # Pip green
GOLD = (255, 200, 61)     # sunshine accent
CREAM = (247, 248, 251)   # light slide background
WHITE = (255, 255, 255)
RED = JADE                # "watch this" tag colour
MUTED = (170, 184, 215)
VIOLET = (123, 77, 255)

PAGE = os.environ.get("PAGE_NAME", "LearnSum")
HANDLE = os.environ.get("PAGE_HANDLE", "learnsum.ca")
TAGLINE = "Learning that feels like play · K to 8"


@lru_cache(maxsize=512)
def font(path, size):
    return ImageFont.truetype(path, max(8, int(size)))


def bg_gradient(w, h, top=GREEN, bottom=INK, t=0.0):
    """Vertical gradient with two slowly drifting glows (computed small, then upscaled)."""
    sw, sh = w // 4, h // 4
    y = np.linspace(0, 1, sh)[:, None]
    x = np.linspace(0, 1, sw)[None, :]
    base = np.array(top)[None, None, :] * (1 - y[..., None]) + np.array(bottom)[None, None, :] * y[..., None]
    asp = w / h
    cx, cy = 0.75 + 0.08 * np.sin(t * 0.6), 0.22 + 0.05 * np.cos(t * 0.5)
    g1 = np.clip(1 - np.sqrt((x - cx) ** 2 * asp ** 2 + (y - cy) ** 2) / 0.55, 0, 1) ** 2
    cx2 = 0.15 + 0.05 * np.cos(t * 0.4)
    g2 = np.clip(1 - np.sqrt((x - cx2) ** 2 * asp ** 2 + (y - 0.85) ** 2) / 0.6, 0, 1) ** 2
    base = base + g1[..., None] * np.array([6, 60, 34]) + g2[..., None] * np.array([40, 22, 70])
    small = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    return small.resize((w, h), Image.BILINEAR).convert("RGBA")


def text_w(d, txt, fnt):
    l, t, r, b = d.textbbox((0, 0), txt, font=fnt)
    return r - l


def wrap(d, txt, fnt, maxw):
    words, lines, cur = txt.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_w(d, trial, fnt) <= maxw:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_size(d, txt, path, size, maxw, min_size=24):
    while size > min_size and text_w(d, txt, font(path, size)) > maxw:
        size -= 2
    return size


def shadowed(im, xy, txt, fnt, fill, anchor="la", blur=8, alpha=160):
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0], xy[1] + 4), txt, font=fnt, fill=(0, 0, 0, alpha), anchor=anchor)
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(im).text(xy, txt, font=fnt, fill=fill, anchor=anchor)


@lru_cache(maxsize=8)
def pip_logo(size):
    """Pip, the LearnSum mascot: a round green sprout with a smile (drawn here, no outside art)."""
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    body = (s * .08, s * .2, s * .92, s * .98)
    d.ellipse(body, fill=(47, 179, 131, 255))
    shine = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(shine).ellipse((s * .2, s * .3, s * .38, s * .44), fill=(255, 255, 255, 60))
    im.alpha_composite(shine)
    d = ImageDraw.Draw(im)
    d.ellipse((s * .3, s * .5, s * .4, s * .62), fill=(19, 32, 29, 255))              # eyes
    d.ellipse((s * .6, s * .5, s * .7, s * .62), fill=(19, 32, 29, 255))
    d.ellipse((s * .33, s * .52, s * .36, s * .55), fill=(255, 255, 255, 255))
    d.ellipse((s * .63, s * .52, s * .66, s * .55), fill=(255, 255, 255, 255))
    d.ellipse((s * .2, s * .64, s * .3, s * .7), fill=(210, 54, 94, 90))              # cheeks
    d.ellipse((s * .7, s * .64, s * .8, s * .7), fill=(210, 54, 94, 90))
    d.arc((s * .38, s * .58, s * .62, s * .76), 20, 160, fill=(19, 32, 29, 255), width=int(s * .035))  # smile
    d.line((s * .5, s * .21, s * .5, s * .08), fill=(20, 163, 90, 255), width=int(s * .04))            # sprout
    d.ellipse((s * .5, s * .02, s * .68, s * .12), fill=GOLD + (255,))
    return im.resize((size, size), Image.LANCZOS)


def badge_logo(size):
    """Pip on a white circle, so it reads on any background."""
    s = size * 2
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((0, 0, s - 1, s - 1), fill=WHITE + (255,))
    p = pip_logo(int(s * .78))
    im.alpha_composite(p, (int(s * .11), int(s * .1)))
    return im.resize((size, size), Image.LANCZOS)


# The shared layouts call coin_logo(); for LearnSum it draws Pip.
coin_logo = badge_logo


APP_DIR = os.path.join(ROOT, "assets", "app")
APP_SHOTS = {f.split("-", 1)[1].rsplit(".", 1)[0]: os.path.join(APP_DIR, f) for f in sorted(os.listdir(APP_DIR))} if os.path.isdir(APP_DIR) else {}


@lru_cache(maxsize=16)
def phone(shot, width):
    """A real LearnSum app screen inside a phone frame. `shot` is one of APP_SHOTS (today, numline, rocket, balance, maker, arcade)."""
    src = Image.open(APP_SHOTS.get(shot) or next(iter(APP_SHOTS.values()))).convert("RGBA")
    pad = int(width * .035)
    inner_w = width - 2 * pad
    inner_h = int(inner_w * src.height / src.width)
    scr = src.resize((inner_w, inner_h), Image.LANCZOS)
    r = int(width * .12)
    mask = Image.new("L", scr.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, inner_w - 1, inner_h - 1), int(r * .8), fill=255)
    out = Image.new("RGBA", (width, inner_h + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle((0, 0, width - 1, inner_h + 2 * pad - 1), r, fill=(10, 15, 31, 255))
    out.paste(scr, (pad, pad), mask)
    sh = Image.new("RGBA", (out.width + 80, out.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((40, 56, out.width + 40, out.height + 56), r, fill=(0, 0, 0, 120))
    sh = sh.filter(ImageFilter.GaussianBlur(22))
    sh.alpha_composite(out, (40, 40))
    return sh
