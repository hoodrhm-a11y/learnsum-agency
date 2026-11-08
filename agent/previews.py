"""Make quick preview images for every spec in a folder (for the weekly approval pull request)."""
import glob, json, os, shutil, sys
from PIL import Image
from engine import render_reel, render_carousel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def reel_preview(spec, out):
    bounds, dur = render_reel.timeline(spec)
    ims = [render_reel.frame(spec, bounds, dur, b - 0.45).convert("RGB").resize((270, 480)) for a, b, _ in bounds]
    sheet = Image.new("RGB", (270 * len(ims), 480))
    for i, m in enumerate(ims):
        sheet.paste(m, (i * 270, 0))
    sheet.save(out, quality=82)
    return dur


def main(folder):
    outdir = os.path.join(ROOT, "previews")
    os.makedirs(outdir, exist_ok=True)
    lines = []
    for p in sorted(glob.glob(os.path.join(folder, "*.json"))):
        s = json.load(open(p))
        out = os.path.join(outdir, s["id"] + ".jpg")
        if s["type"] == "reel":
            d = reel_preview(s, out)
            kind = f"Reel · {d:.0f}s"
        else:
            tmp = os.path.join("/tmp", "prev_" + s["id"])
            render_carousel.render(s, tmp)
            shutil.move(os.path.join(tmp, "preview.jpg"), out)
            kind = f"Carousel · {len(s['slides'])} slides"
        lines.append((s, kind, os.path.relpath(out, ROOT)))
    return lines


if __name__ == "__main__":
    for s, kind, rel in main(sys.argv[1]):
        print(s["publish_at"], kind, rel)
