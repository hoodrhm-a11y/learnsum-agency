"""Render a vertical reel (1080x1920) from a post spec.

Scene kinds: hook, stat, bars, tips, statement, cta.  See README for the spec format.
Usage: python -m engine.render_reel queue/pending/<id>.json  [--preview]
"""
import re
import json, math, os, subprocess, sys, tempfile, zlib
from PIL import Image, ImageDraw, ImageFilter
from engine.brand import *
from engine import music

W, H, FPS = 1080, 1920, 30
X0 = 80
MAXW = W - 2 * X0


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3
def ease_back(x):
    x = clamp(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def enter(lt, start, dur=0.45, dist=60):
    p = ease_out((lt - start) / dur)
    return p, (1 - p) * dist


def txt(im, xy, s, path, size, fill, alpha=1.0, anchor="la", shadow=True):
    if alpha <= 0.01 or not s:
        return
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    fnt = font(path, size)
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((xy[0], xy[1] + 5), s, font=fnt, fill=(0, 0, 0, 150), anchor=anchor)
        layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(9)))
    ImageDraw.Draw(layer).text(xy, s, font=fnt, fill=fill, anchor=anchor)
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    im.alpha_composite(layer)


def rrect(im, box, r, fill, alpha=1.0):
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    a = fill[3] if len(fill) == 4 else 255
    ImageDraw.Draw(layer).rounded_rectangle(box, r, fill=tuple(fill[:3]) + (int(a * alpha),))
    im.alpha_composite(layer)


_D = ImageDraw.Draw(Image.new("RGB", (10, 10)))


def fitted(s, path, size, maxw=MAXW):
    return fit_size(_D, s, path, size, maxw)


# ---------------- scenes ----------------
# each: (duration_fn(scene), draw_fn(im, lt, length, scene))

def d_hook(sc): return 3.2
def s_hook(im, lt, L, sc):
    fo = clamp((L - lt) / 0.3)
    lines = sc["lines"]; acc = sc.get("accent", 1)
    y = 520
    for i, s in enumerate(lines):
        big = i == acc
        path, base = (DISPLAY, 150) if big else (BLACK, 92)
        sz = fitted(s, path, base)
        a, dy = enter(lt, 0.1 + i * 0.28, 0.5, 80)
        scale = 0.85 + 0.15 * ease_back((lt - 0.1 - i * 0.28) / 0.5)
        txt(im, (X0, y + dy), s, path, sz * scale, GOLD if big else WHITE, a * fo)
        y += int(sz * 1.12)
    tag = sc.get("tag", "Watch this first  ↓")
    a, dy = enter(lt, 1.7, 0.5, 40)
    tw = text_w(_D, tag, font(BOLD, 40)) + 80
    rrect(im, (X0, y + 60 + dy, X0 + tw, y + 150 + dy), 45, RED + (255,), a * fo)
    txt(im, (X0 + tw / 2, y + 105 + dy), tag, BOLD, 40, WHITE, a * fo, "mm", shadow=False)


def d_stat(sc): return 4.4
def s_stat(im, lt, L, sc):
    fo = clamp((L - lt) / 0.3)
    chip = sc.get("chip")
    if chip:
        a, dy = enter(lt, 0.0, 0.4, 30)
        cw = text_w(_D, chip, font(SEMI, 30)) + 60
        rrect(im, (X0, 430 + dy, X0 + cw, 500 + dy), 35, (255, 255, 255, 40), a * fo)
        txt(im, (X0 + cw / 2, 465 + dy), chip, SEMI, 30, CREAM, a * fo, "mm", shadow=False)
    v = float(sc["value"]); p = ease_out((lt - 0.3) / 1.3)
    dec = int(sc.get("decimals", 0))
    shown = f"{v * p:,.{dec}f}"
    s = f"{sc.get('prefix', '')}{shown}{sc.get('suffix', '')}"
    final = f"{sc.get('prefix', '')}{v:,.{dec}f}{sc.get('suffix', '')}"
    sz = fitted(final, DISPLAY, 330)
    pop = 1 + 0.08 * math.sin(clamp((lt - 1.6) / 0.35) * math.pi)
    txt(im, (X0 - 10, 540), s, DISPLAY, sz * pop, GOLD, clamp((lt - 0.25) / 0.2) * fo)
    y = 560 + sz * 1.25
    for i, ln in enumerate(sc.get("lines", [])):
        a, dy = enter(lt, 1.4 + i * 0.18, 0.45, 40)
        txt(im, (X0, y + i * 78 + dy), ln, BOLD, fitted(ln, BOLD, 60), WHITE, a * fo)


def d_bars(sc): return 4.8
def s_bars(im, lt, L, sc):
    fo = clamp((L - lt) / 0.3)
    a, dy = enter(lt, 0.0, 0.4, 40)
    t = sc.get("title", ["", ""])
    txt(im, (X0, 380 + dy), t[0], BLACK, fitted(t[0], BLACK, 80), WHITE, a * fo)
    if len(t) > 1:
        txt(im, (X0, 470 + dy), t[1], BLACK, fitted(t[1], BLACK, 80), GOLD, a * fo)
    A, B = float(sc["a"]), float(sc["b"])
    top = max(A, B)
    base_y, unit = 1240, 420 / top
    bw = 300
    a1, _ = enter(lt, 0.4, 0.4, 0)
    h1 = A * unit * ease_out((lt - 0.4) / 0.6)
    rrect(im, (X0, base_y - h1, X0 + bw, base_y), 18, (255, 255, 255, 70), a1 * fo)
    txt(im, (X0 + bw / 2, base_y + 50), sc.get("a_label", ""), SEMI, 36, MUTED, a1 * fo, "mm", shadow=False)
    txt(im, (X0 + bw / 2, base_y - h1 - 40), sc.get("a_value", ""), BOLD, 44, WHITE, clamp((lt - 0.9) / 0.3) * fo, "mm")
    x2 = X0 + bw + 120
    g = ease_out((lt - 1.1) / 1.0)
    h2 = (A + (B - A) * g) * unit * ease_out((lt - 1.1) / 0.5)
    rrect(im, (x2, base_y - h2, x2 + bw, base_y), 18, GOLD + (255,), clamp((lt - 1.1) / 0.2) * fo)
    txt(im, (x2 + bw / 2, base_y + 50), sc.get("b_label", ""), SEMI, 36, MUTED, clamp((lt - 1.1) / 0.3) * fo, "mm", shadow=False)
    pop = ease_back((lt - 2.0) / 0.45)
    txt(im, (x2 + bw / 2, base_y - h2 - 60), sc.get("badge", ""), DISPLAY, 96 * (0.6 + 0.4 * pop), GOLD, clamp((lt - 2.0) / 0.2) * fo, "mm")
    a, dy = enter(lt, 2.6, 0.45, 30)
    txt(im, (X0, 1340 + dy), sc.get("note", ""), MED, 34, MUTED, a * fo, shadow=False)
    ex = sc.get("example")
    if ex:
        ex = re.sub(r"^example\s*:\s*", "Example: ", ex, flags=re.I)
        lines = wrap(ImageDraw.Draw(im), ex, font(BOLD, 36), MAXW - 60)[:3]
        rrect(im, (X0, 1400 + dy, W - X0, 1400 + dy + 40 + 48 * len(lines)), 24, (255, 255, 255, 30), a * fo)
        for k, ln in enumerate(lines):
            txt(im, (X0 + 30, 1420 + dy + 48 * k), ln, BOLD, 36, WHITE, a * fo, shadow=False)


def d_tips(sc): return 1.0 + 1.6 * len(sc["items"]) + 1.6
def s_tips(im, lt, L, sc):
    fo = clamp((L - lt) / 0.3)
    a, dy = enter(lt, 0.0, 0.4, 40)
    t = sc.get("title", ["", ""])
    txt(im, (X0, 360 + dy), t[0], BLACK, fitted(t[0], BLACK, 88), WHITE, a * fo)
    if len(t) > 1:
        txt(im, (X0, 460 + dy), t[1], BLACK, fitted(t[1], BLACK, 88), GOLD, a * fo)
    y = 640
    for i, tip in enumerate(sc["items"]):
        st = 0.5 + i * 1.6
        p = ease_out((lt - st) / 0.5)
        dx = (1 - p) * 300
        lines = wrap(_D, tip, font(BOLD, 46), MAXW - 190)
        hgt = 60 + len(lines) * 58
        rrect(im, (X0 + dx, y, W - X0 + dx, y + hgt), 30, (255, 255, 255, 34), p * fo)
        cx, cy = X0 + 70 + dx, y + hgt / 2
        rrect(im, (cx - 42, cy - 42, cx + 42, cy + 42), 42, GOLD + (255,), p * fo)
        txt(im, (cx, cy), str(i + 1), BLACK, 48, INK, p * fo, "mm", shadow=False)
        for j, ln in enumerate(lines):
            txt(im, (X0 + 150 + dx, y + 30 + j * 58), ln, BOLD, 46, WHITE, p * fo, shadow=False)
        y += hgt + 36


def d_statement(sc): return 1.2 + 0.5 * len(sc["lines"]) + 1.6
def s_statement(im, lt, L, sc):
    fo = clamp((L - lt) / 0.3)
    acc = set(sc.get("accent", []))
    y = 560
    for i, s in enumerate(sc["lines"]):
        sz = fitted(s, BLACK, 96)
        a, dy = enter(lt, 0.1 + i * 0.35, 0.5, 60)
        txt(im, (X0, y + dy), s, BLACK, sz, GOLD if i in acc else WHITE, a * fo)
        y += int(sz * 1.15)
    sub = sc.get("sub")
    if sub:
        a, dy = enter(lt, 0.3 + len(sc["lines"]) * 0.35, 0.5, 40)
        for j, ln in enumerate(wrap(_D, sub, font(SEMI, 44), MAXW)):
            txt(im, (X0, y + 40 + j * 58 + dy), ln, SEMI, 44, CREAM, a * fo)


def d_app(sc): return 4.6
def s_app(im, lt, L, sc):
    """A real app screen in a phone, rising in, with 1-3 short lines above it."""
    fo = clamp((L - lt) / 0.3)
    y = 330
    acc = set(sc.get("accent", [len(sc.get("lines", [])) - 1]))
    for i, ln in enumerate(sc.get("lines", [])):
        a, dy = enter(lt, 0.05 + i * 0.25, 0.45, 50)
        sz = fitted(ln, BLACK, 84)
        txt(im, (X0, y + dy), ln, BLACK, sz, GOLD if i in acc else WHITE, a * fo)
        y += int(sz * 1.15)
    ph = phone(sc.get("shot", "today"), 560)
    p = ease_out((lt - 0.4) / 0.8)
    top = int(max(y + 40, 640) + (1 - p) * 500)
    if p > 0.01:
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        layer.alpha_composite(ph, (int(W / 2 - ph.width / 2), top))
        if fo < 1:
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * fo)))
        im.alpha_composite(layer)
    note = sc.get("note")
    if note:
        a, dy = enter(lt, 1.6, 0.45, 30)
        nw = text_w(_D, note, font(BOLD, 40)) + 80
        rrect(im, (W / 2 - nw / 2, 1700 + dy, W / 2 + nw / 2, 1786 + dy), 43, GOLD + (255,), a * fo)
        txt(im, (W / 2, 1743 + dy), note, BOLD, 40, INK, a * fo, "mm", shadow=False)


def d_cta(sc): return 4.3
def s_cta(im, lt, L, sc):
    pop = ease_back(lt / 0.6)
    if pop > 0.02:
        s = max(1, int(260 * pop))
        lg = coin_logo(260).resize((s, s), Image.LANCZOS)
        im.alpha_composite(lg, (int(W / 2 - s / 2), int(560 - s / 2)))
    a, dy = enter(lt, 0.4, 0.5, 40)
    txt(im, (W / 2, 790 + dy), PAGE, BLACK, 84, WHITE, a, "mm")
    a, dy = enter(lt, 0.7, 0.5, 40)
    txt(im, (W / 2, 900 + dy), "Learning that feels like play", BOLD, 54, CREAM, a, "mm")
    txt(im, (W / 2, 970 + dy), "Kindergarten to grade 8", BOLD, 54, CREAM, a, "mm")
    save = sc.get("save", "Try it free for 14 days")
    a, dy = enter(lt, 1.1, 0.5, 40)
    sw = text_w(_D, save, font(BOLD, 38)) + 100
    rrect(im, (W / 2 - sw / 2, 1060 + dy, W / 2 + sw / 2, 1150 + dy), 45, GOLD + (255,), a)
    txt(im, (W / 2, 1105 + dy), save, BOLD, 38, INK, a, "mm", shadow=False)
    a, _ = enter(lt, 1.5, 0.5, 0)
    txt(im, (W / 2, 1300), "learnsum.ca", BLACK, 56, GOLD, a, "mm")
    src = sc.get("source", "")
    if src:
        txt(im, (W / 2, 1390), src, MED, fitted(src, MED, 28), MUTED, a, "mm", shadow=False)


SCENES = {"hook": (d_hook, s_hook), "stat": (d_stat, s_stat), "bars": (d_bars, s_bars),
          "tips": (d_tips, s_tips), "statement": (d_statement, s_statement), "app": (d_app, s_app), "cta": (d_cta, s_cta)}


def chrome(im, t, dur):
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((X0, 70, W - X0, 78), 4, fill=(255, 255, 255, 50))
    d.rounded_rectangle((X0, 70, X0 + (W - 2 * X0) * (t / dur), 78), 4, fill=GOLD + (255,))
    im.alpha_composite(coin_logo(64), (X0, 110))
    d.text((X0 + 80, 128), PAGE, font=font(BOLD, 34), fill=WHITE)
    d.text((X0 + 80, 166), TAGLINE, font=font(MED, 24), fill=MUTED)


def timeline(spec):
    bounds, t = [], 0.0
    for sc in spec["scenes"]:
        d = SCENES[sc["kind"]][0](sc)
        bounds.append((t, t + d, sc)); t += d
    return bounds, t


def frame(spec, bounds, dur, t):
    im = bg_gradient(W, H, t=t)
    chrome(im, t, dur)
    for a, b, sc in bounds:
        if a <= t < b:
            SCENES[sc["kind"]][1](im, t - a, b - a, sc)
    return im


def render(spec, out_mp4, preview_jpg=None):
    bounds, dur = timeline(spec)
    n = int(dur * FPS)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", tmp],
                         stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(frame(spec, bounds, dur, i / FPS).tobytes())
    p.stdin.close(); p.wait()
    wav = tmp.replace(".mp4", ".wav")
    music.make(dur, wav, seed=zlib.crc32(spec["id"].encode()) % 10000, intro=bounds[0][1])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5", "-shortest", "-movflags", "+faststart", out_mp4],
                   check=True)
    os.remove(tmp); os.remove(wav)
    if preview_jpg:
        ts = [b - 0.45 for a, b, _ in bounds]
        ims = [frame(spec, bounds, dur, t).convert("RGB").resize((270, 480)) for t in ts]
        sheet = Image.new("RGB", (270 * len(ims), 480))
        for i, m in enumerate(ims):
            sheet.paste(m, (i * 270, 0))
        sheet.save(preview_jpg, quality=85)
    return dur


if __name__ == "__main__":
    path = sys.argv[1]
    spec = json.load(open(path))
    base = os.path.splitext(path)[0]
    d = render(spec, base + ".mp4", base + "_preview.jpg")
    print(f"rendered {spec['id']} ({d:.1f}s)")
