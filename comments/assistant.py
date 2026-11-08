"""Comment assistant: hides spam, replies to simple comments, flags anything needing a human.

Looks at comments on posts published in the last 14 days (Facebook + Instagram).
Env: ANTHROPIC_API_KEY, CLAUDE_MODEL, META_* (see publish/meta.py), MAX_REPLIES_PER_RUN (default 25)
Writes: state/comments.json (comment ids only), state/flagged.md (for the GitHub issue; never quotes comments,
because this repository is public)
"""
import datetime as dt, glob, json, os, re
import requests
from publish import meta
from agent.validate import BANNED, NUM, norm, allowed_numbers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state", "comments.json")
FLAGGED = os.path.join(ROOT, "state", "flagged.md")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
MAX_REPLIES = int(os.environ.get("MAX_REPLIES_PER_RUN", 25))

SPAM_PATTERNS = [r"whats?app", r"telegram", r"\+\d{8,}", r"dm me", r"crypto (expert|manager|trader)", r"bitcoin mining",
                 r"invest(ment)? with (mr|mrs|ms)", r"recover(y)? (your )?(lost )?funds", r"earn \$?\d+.*(daily|weekly|per day)",
                 r"click (my|the) (bio|link)", r"forex", r"sugar ?daddy"]

SYSTEM = """You manage comments for "LearnSum", a Canadian learning app for kids from Kindergarten to grade 8 (learnsum.ca).
The page talks to parents. Facts you may use in replies (do not invent any others):
- 14-day free trial with full access, no credit card needed. Then $2.99 CAD a month per child. Cancel any time.
- Kindergarten to grade 8; math, reading, language, writing, listening and safety; more than 800 skills;
  more than 30 learning games and hands-on labs; a daily learning path; a mastery score for every skill.
- Works on iPhone and iPad (App Store, search "LearnSum") and in any web browser at learnsum.ca.
- No ads and no chat. Kids never need an email address; a parent creates the account and the child profiles.
- Help: hello@learnsum.ca.
For each comment, choose one action:
- "hide": spam, scams, links to strangers, harassment, hate, anything sexual or unsafe about children.
- "reply": friendly or simple comments, thanks, and GENERAL questions you can answer in 1-2 short sentences
  (price, ages, devices, "is it safe", how to try it). Warm, plain, Canadian, max 220 characters, at most one emoji.
  You may mention learnsum.ca as plain text (no links with http).
- "flag": questions about a specific child's learning difficulties, behaviour or health; account, billing or refund
  problems; complaints; corrections claiming we're wrong; teachers, schools or media asking about partnerships.
  Still give a short "reply" that thanks them and points to hello@learnsum.ca (billing/account/partnerships) or, for a
  child's specific needs, to their child's teacher or family doctor. Never diagnose or give medical or specialist advice.
- "ignore": the page's own comments, emoji-only comments (you may still reply with a short thanks), anything unclear.
Never promise results. Never ask people to DM. Never share or ask for a child's personal information.
Return ONLY JSON: {"actions": [{"id": "...", "action": "hide|reply|flag|ignore", "reply": "...", "reason": "..."}]}"""


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {"handled": {}}


def recent_posts(days=14):
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    for p in glob.glob(os.path.join(ROOT, "queue", "posted", "*.json")):
        s = json.load(open(p))
        pub = s.get("published", {})
        if pub.get("at") and dt.datetime.fromisoformat(pub["at"]) >= cutoff:
            yield s


def gather(state):
    items = []
    for s in recent_posts():
        pub = s["published"]
        fb_id = pub.get("fb_post_id") or pub.get("fb_video_id")
        if fb_id:
            try:
                for c in meta.fb_comments(fb_id):
                    if c["id"] in state["handled"] or c.get("is_hidden") or (c.get("from") or {}).get("id") == meta.PAGE:
                        continue
                    items.append({"id": c["id"], "platform": "facebook", "post": s["topic"], "text": c.get("message", "")})
            except meta.MetaError as e:
                print("fb comments error", fb_id, e)
        ig_id = pub.get("ig_media_id")
        if ig_id:
            try:
                for c in meta.ig_comments(ig_id):
                    if c["id"] in state["handled"] or c.get("hidden"):
                        continue
                    items.append({"id": c["id"], "platform": "instagram", "post": s["topic"], "text": c.get("text", ""),
                                  "user": c.get("username")})
            except meta.MetaError as e:
                print("ig comments error", ig_id, e)
    return items


def rule_spam(text):
    t = text.lower()
    return any(re.search(p, t) for p in SPAM_PATTERNS)


def ask_claude(items):
    if not items:
        return []
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=300, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 4000, "system": SYSTEM,
              "messages": [{"role": "user", "content": json.dumps(items, ensure_ascii=False)}]})
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")
    return json.loads(re.search(r"\{.*\}", text, re.S).group(0))["actions"]


def safe_reply(text, ok):
    if not text or len(text) > 300:
        return False
    low = text.lower()
    if any(b in low for b in BANNED) or "http" in low or "dm me" in low:
        return False
    return all(norm(t) in ok for t in NUM.findall(text))


def main():
    state = load_state()
    items = gather(state)
    print(f"{len(items)} new comment(s)")
    ok = allowed_numbers()
    by_id = {i["id"]: i for i in items}
    flagged, replies = [], 0
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    spam = [i for i in items if rule_spam(i["text"])]
    rest = [i for i in items if not rule_spam(i["text"])]
    actions = [{"id": i["id"], "action": "hide", "reason": "spam pattern"} for i in spam]
    for k in range(0, len(rest), 40):
        actions += ask_claude(rest[k:k + 40])
    for a in actions:
        c = by_id.get(a.get("id"))
        if not c:
            continue
        fb = c["platform"] == "facebook"
        act = a.get("action")
        try:
            if act == "hide":
                (meta.fb_hide if fb else meta.ig_hide)(c["id"])
            if act in ("reply", "flag") and a.get("reply") and replies < MAX_REPLIES:
                if safe_reply(a["reply"], ok):
                    (meta.fb_reply if fb else meta.ig_reply)(c["id"], a["reply"]); replies += 1; a["_sent"] = True
                else:
                    act = "flag"; a["reason"] = (a.get("reason") or "") + " (reply blocked by safety check)"
            if act == "flag":
                # This repository is public, so the alert never quotes the comment or names the person.
                flagged.append(f"- A comment on **{c['platform']}** under *{c['post']}* needs you. Open the post on the LearnSum Page to read it."
                               + (" A short polite reply was already sent." if a.get("_sent") else ""))
            state["handled"][c["id"]] = {"action": act, "at": now}
        except meta.MetaError as e:
            print("action failed", c["id"], e)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, "w"), indent=1)
    open(FLAGGED, "w").write("\n".join(flagged))
    print(f"replied {replies}, hid {sum(1 for a in actions if a.get('action') == 'hide')}, flagged {len(flagged)}")


if __name__ == "__main__":
    main()
