"""Publish every approved post whose time has come (within a 12-minute look-ahead).

python -m publish.publish_due            # render + post
python -m publish.publish_due --check    # only print how many are due (exit 0 if some due, 3 if none)
DRY_RUN=1 renders without posting.
"""
import datetime as dt, glob, json, os, shutil, sys, tempfile, traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPROVED = os.path.join(ROOT, "queue", "approved")
POSTED = os.path.join(ROOT, "queue", "posted")
LOOKAHEAD = dt.timedelta(minutes=12)


def due():
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for p in sorted(glob.glob(os.path.join(APPROVED, "*.json"))):
        s = json.load(open(p))
        if dt.datetime.fromisoformat(s["publish_at"]) <= now + LOOKAHEAD:
            out.append((p, s))
    return out


def publish_one(path, spec):
    from publish import meta, storage
    from engine import render_reel, render_carousel
    work = tempfile.mkdtemp()
    caption = spec["caption"]
    result = dict(spec.get("partial", {}))  # what already went out on a previous attempt

    def save():
        spec["partial"] = result
        json.dump(spec, open(path, "w"), indent=1, ensure_ascii=False)

    if spec["type"] == "reel":
        mp4 = os.path.join(work, spec["id"] + ".mp4")
        render_reel.render(spec, mp4)
        if os.environ.get("DRY_RUN"):
            return {"dry_run": mp4}
        if "fb_video_id" not in result:
            result.update(meta.fb_reel(mp4, caption)); save()
        if meta.IG and storage.enabled() and "ig_media_id" not in result:
            url = storage.upload(mp4, f"reels/{spec['id']}.mp4")
            result.update(meta.ig_reel(url, caption))
    else:
        files = render_carousel.render(spec, work)
        if os.environ.get("DRY_RUN"):
            return {"dry_run": files}
        if "fb_post_id" not in result:
            result.update(meta.fb_carousel(files, caption)); save()
        if meta.IG and storage.enabled() and "ig_media_id" not in result:
            urls = [storage.upload(f, f"carousels/{spec['id']}/{os.path.basename(f)}") for f in files]
            result.update(meta.ig_carousel(urls, caption))
    shutil.rmtree(work, ignore_errors=True)
    return result


def main():
    items = due()
    if "--check" in sys.argv:
        print(f"{len(items)} post(s) due")
        sys.exit(0 if items else 3)
    failed = 0
    os.makedirs(POSTED, exist_ok=True)
    for path, spec in items:
        try:
            res = publish_one(path, spec)
            if os.environ.get("DRY_RUN"):
                print("DRY RUN", spec["id"], res); continue
            spec["published"] = {**res, "at": dt.datetime.now(dt.timezone.utc).isoformat()}
            spec.pop("last_error", None); spec.pop("partial", None)
            json.dump(spec, open(os.path.join(POSTED, os.path.basename(path)), "w"), indent=1, ensure_ascii=False)
            os.remove(path)
            print("posted", spec["id"], res)
        except Exception as e:
            failed += 1
            spec["last_error"] = f"{dt.datetime.now(dt.timezone.utc).isoformat()} {e}"
            json.dump(spec, open(path, "w"), indent=1, ensure_ascii=False)
            traceback.print_exc()
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
