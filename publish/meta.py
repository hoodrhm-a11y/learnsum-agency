"""Minimal Meta Graph API client for one Facebook Page + its linked Instagram account.

Env: META_PAGE_ID, META_PAGE_TOKEN (long-lived Page access token), META_IG_USER_ID (optional),
     META_API_VERSION (default v23.0)
"""
import json, os, time
import requests

V = os.environ.get("META_API_VERSION", "v27.0")
G = f"https://graph.facebook.com/{V}"
PAGE = os.environ.get("META_PAGE_ID", "")
TOKEN = os.environ.get("META_PAGE_TOKEN", "")
IG = os.environ.get("META_IG_USER_ID", "")


class MetaError(RuntimeError):
    pass


def _req(method, url, **kw):
    params = kw.pop("params", {})
    params.setdefault("access_token", TOKEN)
    r = requests.request(method, url, params=params, timeout=300, **kw)
    try:
        j = r.json()
    except Exception:
        j = {"raw": r.text}
    if r.status_code >= 400 or (isinstance(j, dict) and "error" in j):
        raise MetaError(f"{method} {url.split('?')[0]} -> {r.status_code}: {json.dumps(j)[:500]}")
    return j


def get(path, **params): return _req("GET", f"{G}/{path}", params=params)
def post(path, data=None, files=None, **params): return _req("POST", f"{G}/{path}", params=params, data=data, files=files)


# ---------------- Facebook ----------------
def fb_reel(video_path, caption):
    start = post(f"{PAGE}/video_reels", upload_phase="start")
    vid = start["video_id"]
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        r = requests.post(start.get("upload_url", f"https://rupload.facebook.com/video-upload/{V}/{vid}"),
                          headers={"Authorization": f"OAuth {TOKEN}", "offset": "0", "file_size": str(size)},
                          data=f, timeout=600)
    if r.status_code >= 400:
        raise MetaError(f"reel upload failed: {r.status_code} {r.text[:300]}")
    post(f"{PAGE}/video_reels", upload_phase="finish", video_id=vid, video_state="PUBLISHED", description=caption)
    return {"fb_video_id": vid}


def fb_carousel(image_paths, caption):
    ids = []
    for p in image_paths:
        with open(p, "rb") as f:
            ids.append(post(f"{PAGE}/photos", data={"published": "false"}, files={"source": f})["id"])
    data = {"message": caption}
    for i, mid in enumerate(ids):
        data[f"attached_media[{i}]"] = json.dumps({"media_fbid": mid})
    res = post(f"{PAGE}/feed", data=data)
    return {"fb_post_id": res["id"]}


# ---------------- Instagram (needs public media URLs) ----------------
def _ig_wait(container, tries=60):
    for _ in range(tries):
        st = get(container, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise MetaError(f"IG container {container} status {st}")
        time.sleep(10)
    raise MetaError("IG container timed out")


def ig_reel(video_url, caption):
    c = post(f"{IG}/media", data={"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true"})["id"]
    _ig_wait(c)
    return {"ig_media_id": post(f"{IG}/media_publish", data={"creation_id": c})["id"]}


def ig_carousel(image_urls, caption):
    kids = [post(f"{IG}/media", data={"image_url": u, "is_carousel_item": "true"})["id"] for u in image_urls]
    for k in kids:
        _ig_wait(k)
    c = post(f"{IG}/media", data={"media_type": "CAROUSEL", "children": ",".join(kids), "caption": caption})["id"]
    _ig_wait(c)
    return {"ig_media_id": post(f"{IG}/media_publish", data={"creation_id": c})["id"]}


# ---------------- Comments ----------------
def fb_comments(object_id):
    return get(f"{object_id}/comments", fields="id,message,from,created_time,is_hidden", filter="stream", limit=100).get("data", [])


def fb_reply(comment_id, text): return post(f"{comment_id}/comments", data={"message": text})
def fb_hide(comment_id): return post(comment_id, data={"is_hidden": "true"})


def ig_comments(media_id):
    return get(f"{media_id}/comments", fields="id,text,username,timestamp,hidden", limit=100).get("data", [])


def ig_reply(comment_id, text): return post(f"{comment_id}/replies", data={"message": text})
def ig_hide(comment_id): return post(comment_id, data={"hide": "true"})


# ---------------- Insights (best effort; metric names change between API versions) ----------------
def safe_metrics(object_id, metrics, edge="insights"):
    out = {}
    for m in metrics:
        try:
            data = get(f"{object_id}/{edge}", metric=m).get("data", [])
            if data:
                vals = data[0].get("values") or [{}]
                out[m] = vals[0].get("value", data[0].get("total_value", {}).get("value"))
        except MetaError:
            pass
    return out
