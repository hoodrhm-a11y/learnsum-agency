"""Render a carousel (1080x1350 slides) from a post spec.

Slide kinds: cover, points, compare, cta.  See README for the spec format.
Usage: python -m engine.render_carousel queue/pending/<id>.json
"""
import json, os, re, sys
from PIL import Image, ImageDraw
from engine.brand import *

W, H = 1080, 1350
M = 90


def footer(im, i, n, dark):
    d = ImageDraw.Draw(im)
    col = MUTED if dark else (90, 100, 130)
    im.alpha_composite(coin_logo(48), (M, H - 100))
    d.text((M + 62, H - 76), HANDLE, font=font(SEMI, 28), fill=col, anchor="lm")
    for k in range(n):
        x = W / 2 - (n - 1) * 14 + k * 28
        c = (GOLD if dark else JADE) if k == i else ((255, 255, 255, 70) if dark else (19, 32, 74, 60))
        d.ellipse((x - 6, H - 82, x + 6, H - 70), fill=c)
    if i < n - 1:
        d.text((W - M, H - 76), "Swipe  →", font=font(BOLD, 30), fill=GOLD if dark else JADE, anchor="rm")


def cover(s, i, n):
    im = bg_gradient(W, H)
    d = ImageDraw.Draw(im)
    chip = s.get("chip", "For parents · K to 8")
    cw = text_w(d, chip, font(SEMI, 30)) + 60
    lay = Image.new("RGBA", im.size); ImageDraw.Draw(lay).rounded_rectangle((M, 150, M + cw, 210), 30, fill=(255, 255, 255, 40)); im.alpha_composite(lay)
    d.text((M + cw / 2, 180), chip, font=font(SEMI, 30), fill=CREAM, anchor="mm")
    y = 330
    acc = s.get("accent", 1)
    for k, ln in enumerate(s["title"]):
        sz = fit_size(d, ln, DISPLAY, 128, W - 2 * M)
        shadowed(im, (M, y), ln, font(DISPLAY, sz), GOLD if k == acc else WHITE)
        y += int(sz * 1.13)
    for ln in wrap(d, s.get("sub", ""), font(BOLD, 50), W - 2 * M):
        shadowed(im, (M, y + 40), ln, font(BOLD, 50), CREAM); y += 64
    footer(im, i, n, True)
    return im


def points(s, i, n):
    im = Image.new("RGBA", (W, H), CREAM + (255,))
    d = ImageDraw.Draw(im)
    if s.get("mark"):
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((W - M + 10, 1010), str(s["mark"]), font=font(DISPLAY, 420), fill=(255, 200, 61, 90), anchor="rs")
        im.alpha_composite(lay); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 14), fill=JADE)
    d.text((M, 120), s.get("kicker", "").upper(), font=font(BOLD, 30), fill=JADE)
    y = 175
    for ln in wrap(d, s["title"], font(BLACK, 76), W - 2 * M):
        d.text((M, y), ln, font=font(BLACK, 76), fill=GREEN); y += 88
    y += 40
    for big, small in s.get("items", []):
        if big:
            d.rounded_rectangle((M, y, W - M, y + 8), 4, fill=(19, 32, 74, 22))
            y += 34
            for ln in wrap(d, big, font(XBOLD, 54), W - 2 * M):
                d.text((M, y), ln, font=font(XBOLD, 54), fill=INK); y += 64
        for ln in wrap(d, small, font(MED, 38), W - 2 * M):
            d.text((M, y + 6), ln, font=font(MED, 38), fill=(70, 82, 112)); y += 50
        y += 34
    note = s.get("note")
    ex = s.get("example")
    if ex and note:
        nl = wrap(d, note, font(MED, 28), W - 2 * M)
        y += 0
        for ln in nl:
            d.text((M, y), ln, font=font(MED, 28), fill=(110, 120, 145)); y += 38
        y += 10
        note = None
    if ex:
        ex = re.sub(r"^example\s*:\s*", "", ex, flags=re.I)
        lines = wrap(d, ex, font(SEMI, 40), W - 2 * M - 80)
        bh = 100 + len(lines) * 52
        top = max(y + 10, H - 170 - bh)
        d.rounded_rectangle((M, top, W - M, top + bh), 30, fill=WHITE, outline=(19, 32, 74, 40), width=2)
        d.text((M + 40, top + 32), "EXAMPLE", font=font(BOLD, 28), fill=JADE)
        for k, ln in enumerate(lines):
            d.text((M + 40, top + 76 + k * 52), ln, font=font(SEMI, 40), fill=INK)
    if note:
        d.text((M, H - 190), note, font=font(MED, 28), fill=(110, 120, 145))
    footer(im, i, n, False)
    return im


def compare(s, i, n):
    im = Image.new("RGBA", (W, H), CREAM + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 14), fill=JADE)
    d.text((M, 120), s.get("kicker", "").upper(), font=font(BOLD, 30), fill=JADE)
    d.text((M, 175), s["title"], font=font(BLACK, fit_size(d, s["title"], BLACK, 76, W - 2 * M)), fill=GREEN)
    cw = (W - 2 * M - 40) / 2
    for k, side in enumerate([s["left"], s["right"]]):
        col = GREEN if k == 0 else JADE
        x = M + k * (cw + 40)
        d.rounded_rectangle((x, 320, x + cw, 1130), 34, fill=WHITE)
        d.rounded_rectangle((x, 320, x + cw, 430), 34, fill=col)
        d.rectangle((x, 400, x + cw, 430), fill=col)
        d.text((x + cw / 2, 375), side["name"], font=font(BLACK, fit_size(d, side["name"], BLACK, 60, cw - 40)), fill=WHITE, anchor="mm")
        y = 470
        for p in side["points"]:
            d.ellipse((x + 30, y + 14, x + 46, y + 30), fill=col)
            for ln in wrap(d, p, font(SEMI, 36), cw - 90):
                d.text((x + 64, y), ln, font=font(SEMI, 36), fill=INK); y += 46
            y += 34
    if s.get("footer"):
        d.text((M, 1170), s["footer"], font=font(MED, 32), fill=(70, 82, 112))
    footer(im, i, n, False)
    return im


def app(s, i, n):
    """A real app screen in a phone, with a short title and caption (for 'see it in action' slides)."""
    im = bg_gradient(W, H)
    d = ImageDraw.Draw(im)
    d.text((M, 110), s.get("kicker", "Inside LearnSum").upper(), font=font(BOLD, 30), fill=GOLD)
    y = 160
    for ln in wrap(d, s["title"], font(BLACK, 70), W - 2 * M):
        shadowed(im, (M, y), ln, font(BLACK, 70), WHITE); y += 82
    ph = phone(s.get("shot", "today"), 470)
    top = max(y + 30, 360)
    crop = ph.crop((0, 0, ph.width, min(ph.height, H - 150 - top)))
    im.alpha_composite(crop, (int(W / 2 - ph.width / 2), top))
    note = s.get("note")
    if note:
        nw = text_w(d, note, font(BOLD, 34)) + 70
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(lay).rounded_rectangle((W / 2 - nw / 2, H - 230, W / 2 + nw / 2, H - 160), 35, fill=GOLD + (255,))
        im.alpha_composite(lay)
        ImageDraw.Draw(im).text((W / 2, H - 195), note, font=font(BOLD, 34), fill=INK, anchor="mm")
    footer(im, i, n, True)
    return im


def cta(s, i, n):
    im = bg_gradient(W, H)
    d = ImageDraw.Draw(im)
    im.alpha_composite(coin_logo(200), (int(W / 2 - 100), 250))
    shadowed(im, (W / 2, 540), PAGE, font(BLACK, 80), WHITE, anchor="mm")
    shadowed(im, (W / 2, 640), "Learning that feels like play", font(BOLD, 52), CREAM, anchor="mm")
    shadowed(im, (W / 2, 706), "Kindergarten to grade 8", font(BOLD, 52), CREAM, anchor="mm")
    d.rounded_rectangle((W / 2 - 330, 790, W / 2 + 330, 880), 45, fill=GOLD)
    sv = s.get("save", "Try it free for 14 days")
    d.text((W / 2, 835), sv, font=font(BOLD, fit_size(d, sv, BOLD, 36, 600)), fill=INK, anchor="mm")
    shadowed(im, (W / 2, 950), "learnsum.ca", font(BLACK, 56), GOLD, anchor="mm")
    y = 1040
    for ln in s.get("lines", []):
        d.text((W / 2, y), ln, font=font(MED, fit_size(d, ln, MED, 27, W - 2 * M)), fill=MUTED, anchor="mm"); y += 40
    footer(im, i, n, True)
    return im


KINDS = {"cover": cover, "points": points, "compare": compare, "app": app, "cta": cta}


def render(spec, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    slides = spec["slides"]
    files, ims = [], []
    for k, s in enumerate(slides):
        im = KINDS[s["kind"]](s, k, len(slides)).convert("RGB")
        f = os.path.join(out_dir, f"{k + 1:02d}.jpg")
        im.save(f, quality=92); files.append(f); ims.append(im)
    sheet = Image.new("RGB", (270 * len(ims), 338), "white")
    for k, im in enumerate(ims):
        sheet.paste(im.resize((270, 338)), (k * 270, 0))
    sheet.save(os.path.join(out_dir, "preview.jpg"), quality=85)
    return files


if __name__ == "__main__":
    path = sys.argv[1]
    spec = json.load(open(path))
    files = render(spec, os.path.splitext(path)[0])
    print(f"rendered {spec['id']}: {len(files)} slides")
