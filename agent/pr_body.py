"""Builds the weekly approval pull-request description with preview images."""
import json, os, sys, datetime as dt
from agent.previews import main as make_previews

repo, branch, folder = sys.argv[1], sys.argv[2], sys.argv[3]
items = make_previews(folder)
out = ["## 📅 LearnSum — next week's posts", "",
       "**To approve everything:** tap **Merge pull request**. Posts go out automatically at the times below.",
       "**To drop a post:** open *Files changed*, delete that post's `.json` file, then merge.",
       "**To change something:** leave a comment here describing the change, and ask Claude to apply it.", ""]
for s, kind, rel in sorted(items, key=lambda x: x[0]["publish_at"]):
    when = dt.datetime.fromisoformat(s["publish_at"]).strftime("%a %b %-d, %-I:%M %p")
    out += [f"### {when} — {s['topic']}", f"_{kind}_", "",
            f"![{s['id']}](https://github.com/{repo}/blob/{branch}/{rel}?raw=true)", "",
            "<details><summary>Caption</summary>", "", s["caption"], "", "</details>",
            f"<sub>Facts used: {', '.join(s.get('fact_ids', []))}</sub>", ""]
print("\n".join(out))
