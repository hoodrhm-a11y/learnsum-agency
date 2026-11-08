"""Weekly performance check: pulls views/engagement for recent posts, saves state/performance.json,
and writes state/report.md (posted as a GitHub issue so you get it on your phone)."""
import datetime as dt, glob, json, os
from publish import meta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FB_REEL = ["blue_reels_play_count", "post_impressions_unique", "post_video_social_actions"]
FB_POST = ["post_media_view", "post_impressions_unique", "post_clicks"]
IG = ["views", "reach", "saved", "shares", "likes", "comments"]


def main():
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=28)
    rows = []
    for p in glob.glob(os.path.join(ROOT, "queue", "posted", "*.json")):
        s = json.load(open(p))
        pub = s.get("published", {})
        if not pub.get("at") or dt.datetime.fromisoformat(pub["at"]) < cutoff:
            continue
        m = {}
        if pub.get("fb_video_id"):
            m["fb"] = meta.safe_metrics(pub["fb_video_id"], FB_REEL, edge="video_insights")
        if pub.get("fb_post_id"):
            m["fb"] = meta.safe_metrics(pub["fb_post_id"], FB_POST)
        if pub.get("ig_media_id"):
            m["ig"] = meta.safe_metrics(pub["ig_media_id"], IG)
        hook = (s.get("scenes") or s.get("slides"))[0]
        hook_text = " ".join(hook.get("lines") or hook.get("title") or [])
        reach = sum(v for d in m.values() for k, v in d.items() if isinstance(v, (int, float)) and k in
                    ("blue_reels_play_count", "post_media_view", "views", "post_impressions_unique"))
        rows.append({"id": s["id"], "type": s["type"], "topic": s.get("topic"), "hook": hook_text, "score": reach, "metrics": m})
    rows.sort(key=lambda r: -r["score"])
    os.makedirs(os.path.join(ROOT, "state"), exist_ok=True)
    json.dump(rows, open(os.path.join(ROOT, "state", "performance.json"), "w"), indent=1, ensure_ascii=False)
    lines = ["## LearnSum — last 28 days", "", f"Posts tracked: {len(rows)}", "", "### Top posts"]
    for r in rows[:5]:
        lines.append(f"- **{r['topic']}** ({r['type']}) — views/reach: {r['score']:,}  \n  Hook: “{r['hook']}”")
    if rows[5:]:
        lines += ["", "### Weakest posts"] + [f"- {r['topic']} — {r['score']:,}" for r in rows[-3:]]
    lines += ["", "_Next week's plan will lean toward the topics and hooks at the top._"]
    open(os.path.join(ROOT, "state", "report.md"), "w").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
