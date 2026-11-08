"""Plan next week's posts with Claude, validate them, and write specs to queue/pending/.

Env: ANTHROPIC_API_KEY (required), CLAUDE_MODEL (default claude-sonnet-5-5),
     REELS_PER_WEEK (4), CAROUSELS_PER_WEEK (3), START_DATE (YYYY-MM-DD, default next Monday)
Light schedule: one post a day at 7:30 pm Toronto (after dinner, when parents scroll).
"""
import datetime as dt, json, os, re, sys, glob
from zoneinfo import ZoneInfo
import requests, yaml
from agent.validate import check, allowed_numbers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = ZoneInfo("America/Toronto")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
REELS = int(os.environ.get("REELS_PER_WEEK", 4))
CAROUSELS = int(os.environ.get("CAROUSELS_PER_WEEK", 3))
POST_TIME = (19, 30)       # 7:30 pm Toronto, one post a day
CAROUSEL_DAYS = [1, 3, 5]  # Tue, Thu, Sat


def load(p): return open(os.path.join(ROOT, p)).read()


def schedule(start):
    slots = []
    for d in range(min(7, REELS + CAROUSELS)):
        day = start + dt.timedelta(days=d)
        kind = "carousel" if d in CAROUSEL_DAYS[:CAROUSELS] else "reel"
        slots.append((kind, dt.datetime(day.year, day.month, day.day, *POST_TIME, tzinfo=TZ)))
    return slots


def recent_topics():
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "queue", "*", "*.json")))[-40:]:
        try:
            s = json.load(open(p)); out.append(s.get("topic", s["id"]))
        except Exception:
            pass
    return out


def performance():
    p = os.path.join(ROOT, "state", "performance.json")
    return json.load(open(p)) if os.path.exists(p) else []


SYSTEM = """You are the content lead for "LearnSum", a Canadian learning app for kids from Kindergarten to grade 8
(math, reading, language, writing, listening and safety; games, hands-on labs and a daily learning path; learnsum.ca).
The Facebook/Instagram page talks to PARENTS (mostly moms and dads of 4 to 13 year olds in Canada, many in Ontario).

Goal: original, warm, genuinely useful posts that busy parents SAVE and SEND to another parent. Every post should leave
a parent with something they can do tonight in 5-10 minutes. Brand voice: a kind, organised teacher friend. Calm,
encouraging, never preachy, never guilt-tripping, never fear-based.

CONTENT MIX each week (rotate; never two of the same kind in a row):
- At-home learning games and tips with no special materials (cooking math, car-ride word games, bedtime story questions).
- "What your child learns in grade X" explainers (only general, widely taught skills; no invented curriculum codes).
- Myth vs fact about learning (only with facts from the FACTS list, or as clearly general advice without numbers).
- Healthy routines: sleep, activity, screen balance (ONLY using the official CSEP facts in the FACTS list).
- School-year moments from the SEASONAL THEMES (progress reports, winter break, I Love to Read Month, March Break...).
- At most 2 posts a week may show LearnSum itself (use an "app" scene or slide with a real screen: today = daily map,
  numline = Number Line Lab, rocket = Rocket Launch game, balance = Balance Lab algebra, maker = make your own character,
  arcade = game arcade). Show, don't hard-sell: one clear benefit, then "Try it free for 14 days".

HARD RULES (posts that break these are rejected automatically):
- Use ONLY numbers that appear in the FACTS list. Do not invent statistics, research findings, ages, minutes or prices.
  The only exception: a field named "example" may contain illustrative examples and must start with "Example".
- List the ids of every fact you used in "fact_ids" (for a tips post with no numbers, list the closest related fact).
- Never diagnose or mention learning disabilities, ADHD, autism or medical conditions; never promise results
  ("your child will be top of the class", "boost IQ"). Never shame children or parents ("lazy", "falling behind").
- No real children's photos or names of real people; examples use simple first names (Maya, Leo, Aisha, Sam, Omar).
- Plain words a tired parent understands at a glance. Short lines. Canadian spelling (colour, practise as a verb).
- VIRAL PLAYBOOK (Facebook 2026 ranking rewards watch time/completion, shares, saves, comments and originality;
  it punishes clickbait that doesn't deliver and engagement bait):
  * Reel hook = first scene. It must name a real parent moment in under 8 words (homework fights, "what did you do at
    school?" "nothing", screen-time battles, bedtime, report cards). The payoff arrives in the next scene.
  * Formats to rotate: "3 games for [moment]", "Try this tonight", "Instead of X, try Y", myth vs fact,
    "What your grade X child is learning", "One question that gets kids talking", quick routine checklist.
  * Keep reels tight (about 20-30 seconds), one idea per post, zero filler. Completion beats length.
  * CTA = save it, or send it to a parent it helps. Never "tag 3 friends", "comment YES", "like if", "share if you agree".
- Captions: first line repeats the hook in plain words; 2-4 short lines of value; ONE genuine question parents can
  answer from their own life (e.g. "What's your go-to car game?"); for app posts end with "Try LearnSum free for 14 days at
  learnsum.ca"; 3-5 relevant hashtags (#ParentingTips #LearningThroughPlay #Kindergarten #EarlyLearning #CanadianParents).
- VARIETY: at least 4 different content kinds and at least 3 different grade bands (K-2, 3-5, 6-8) across the week.
  Never reuse a headline fact used elsewhere this week (see PLANNED THIS WEEK).

OUTPUT: a single JSON object {"posts": [...]} and nothing else."""


def build_prompt(slots, facts, calendar, topics, perf, week=()):
    week = list(week)
    ex_reel = json.load(open(os.path.join(ROOT, "examples", "reel_counting_dinner.json")))
    ex_car = json.load(open(os.path.join(ROOT, "examples", "carousel_progress_report.json")))
    want = [{"type": t, "publish_at": d.isoformat()} for t, d in slots]
    return f"""FACTS (the only numbers you may use):
{yaml.safe_dump(facts, sort_keys=False, allow_unicode=True)}

SEASONAL THEMES:
{yaml.safe_dump(calendar, sort_keys=False)}
Today is {dt.date.today().isoformat()}.

RECENT TOPICS (avoid repeating these too closely):
{json.dumps(topics)}

PLANNED THIS WEEK (topic, facts used; do not repeat their headline facts):
{json.dumps(week, ensure_ascii=False)}

PAST PERFORMANCE (make more of what worked):
{json.dumps(perf[-20:])}

SLOTS TO FILL, in order (keep type and publish_at exactly):
{json.dumps(want, indent=1)}

FORMAT — reels use scenes: hook (lines[3], accent index, tag), stat (chip, value, prefix, suffix, decimals, lines),
bars (title[2], a, b, a_label, b_label, a_value, badge, note, example), tips (title[2], items[2-3], each under 55 characters),
statement (lines[2-4], accent [indexes], sub), app (lines[1-3] each under 22 characters, accent [indexes], shot, note under 30 characters),
cta (save, source). Reels: hook first, cta last, 4-6 scenes total.
Carousels use slides: cover (chip, title[1-3 short lines], accent, sub), points (kicker, title, items [[big, small]...],
example, mark, note), compare (kicker, title, left{{name, points[3]}}, right{{name, points[3]}}, footer),
app (kicker, title under 40 characters, shot, note under 30 characters), cta (save, lines[sources]).
Carousels: cover first, cta last, 5-7 slides. Keep every text line short enough to read on a phone.

Each post also needs: "id" (YYYY-MM-DD-short-slug using the publish date), "topic" (5-8 words), "caption", "fact_ids".

EXAMPLE REEL:
{json.dumps(ex_reel, indent=1)}

EXAMPLE CAROUSEL:
{json.dumps(ex_car, indent=1)}
"""


def ask(messages):
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=600, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 16000, "system": SYSTEM, "messages": messages})
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0))["posts"]


def plan_chunk(chunk, facts, calendar, topics, perf, ok, week=()):
    messages = [{"role": "user", "content": build_prompt(chunk, facts, calendar, topics, perf, week)}]
    good = {}
    for attempt in range(3):
        text = ask(messages)
        try:
            posts = parse(text)
        except Exception as e:
            messages += [{"role": "assistant", "content": text}, {"role": "user", "content": f"That was not valid JSON ({e}). Return only the JSON object."}]
            continue
        problems = []
        for p in posts:
            errs = check(p, ok)
            if errs:
                problems.append({"id": p.get("id"), "errors": errs})
            else:
                good[p["publish_at"]] = p
        missing = [s for s in chunk if s[1].isoformat() not in good]
        if not missing:
            break
        messages += [{"role": "assistant", "content": text}, {"role": "user", "content":
                      "Some posts failed validation. Fix ONLY these and return {\"posts\": [...]} with the corrected posts:\n"
                      + json.dumps(problems, indent=1) + "\nStill needed slots: " + json.dumps([[t, d.isoformat()] for t, d in missing])}]
    return good


def main():
    today = dt.date.today()
    start = dt.date.fromisoformat(os.environ["START_DATE"]) if os.environ.get("START_DATE") else today + dt.timedelta(days=(7 - today.weekday()) % 7 or 7)
    if not os.environ.get("START_DATE"):
        import glob as _g
        taken = set()
        for f in _g.glob("queue/approved/*.json"):
            try: taken.add(dt.date.fromisoformat(json.load(open(f))["publish_at"][:10]))
            except Exception: pass
        while any(start <= d < start + dt.timedelta(days=7) for d in taken):
            start += dt.timedelta(days=7)
    slots = schedule(start)
    facts = yaml.safe_load(load("agent/facts.yaml"))
    calendar = yaml.safe_load(load("agent/calendar.yaml"))
    ok = allowed_numbers()
    topics, perf = recent_topics(), performance()
    good, week = {}, []
    for k in range(0, len(slots), 3):
        chunk = slots[k:k + 3]
        got = plan_chunk(chunk, facts, calendar, topics, perf, ok, week)
        good.update(got)
        topics += [p.get("topic", p["id"]) for p in got.values()]
        week += [{"topic": p.get("topic"), "type": p["type"], "facts": p.get("fact_ids", [])} for p in got.values()]
        print(f"  planned {len(got)}/{len(chunk)} for {[d.strftime('%a %H:%M') for _, d in chunk]}")
    out = os.path.join(ROOT, "queue", "pending")
    os.makedirs(out, exist_ok=True)
    for p in good.values():
        json.dump(p, open(os.path.join(out, p["id"] + ".json"), "w"), indent=1, ensure_ascii=False)
    print(f"planned {len(good)}/{len(slots)} posts for week of {start}")
    if not good:
        sys.exit(1)


if __name__ == "__main__":
    main()
