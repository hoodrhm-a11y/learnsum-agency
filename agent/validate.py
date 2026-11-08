"""Safety checks every post must pass before it can be rendered or published.

1. Every number in the post must come from agent/facts.yaml (or be a small list number / year).
   Fields named "example" may contain illustrative amounts, but they must start with "Example".
2. Banned phrases (get-rich-quick, guarantees, personal advice) are rejected.
3. Structure must match what the renderer supports.
"""
import re, yaml, os

HERE = os.path.dirname(os.path.abspath(__file__))
NUM = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")
BANNED = ["guaranteed", "guarantee", "genius", "top of the class", "straight a", "boost iq", "raise iq", "smarter in",
          " cure ", "adhd", "dyslexia", "autism", "diagnos", "teachers hate", "secret trick", "act now", "100% safe",
          "only app", "best app", "no.1", "number one app", "#1 app", "lazy", "behind their peers", "falling behind"]
REEL_KINDS = {"hook", "stat", "bars", "tips", "statement", "app", "cta"}
SLIDE_KINDS = {"cover", "points", "compare", "app", "cta"}


def norm(tok):
    return tok.replace("$", "").replace(",", "").replace("%", "").rstrip(".")


def allowed_numbers():
    facts = yaml.safe_load(open(os.path.join(HERE, "facts.yaml")))
    ok = {str(i) for i in range(0, 11)} | {str(y) for y in range(2024, 2029)} | {str(y) for y in range(24, 29)}
    for f in facts:
        for n in f.get("numbers", []):
            for tok in NUM.findall(n):
                ok.add(norm(tok))
        for tok in NUM.findall(f["text"]):
            ok.add(norm(tok))
    return ok


def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def check(spec, ok=None):
    ok = ok or allowed_numbers()
    errs = []
    if spec.get("type") == "reel":
        kinds = [s.get("kind") for s in spec.get("scenes", [])]
        if not kinds or kinds[0] != "hook" or kinds[-1] != "cta":
            errs.append("reel must start with a hook scene and end with a cta scene")
        bad = set(kinds) - REEL_KINDS
        if bad: errs.append(f"unknown scene kinds {bad}")
    elif spec.get("type") == "carousel":
        kinds = [s.get("kind") for s in spec.get("slides", [])]
        if not kinds or kinds[0] != "cover" or kinds[-1] != "cta":
            errs.append("carousel must start with cover and end with cta")
        bad = set(kinds) - SLIDE_KINDS
        if bad: errs.append(f"unknown slide kinds {bad}")
        if not 4 <= len(kinds) <= 10: errs.append("carousel needs 4-10 slides")
    else:
        errs.append("type must be reel or carousel")
    if not spec.get("caption"): errs.append("missing caption")
    if not spec.get("fact_ids"): errs.append("fact_ids must list the facts used")
    for path, v in walk(spec):
        if path.split(".")[-1] in ("id", "publish_at", "fact_ids", "kind", "accent", "decimals", "mark", "a", "b", "a_value", "source", "shot") or "fact_ids" in path:
            continue
        s = str(v)
        low = s.lower()
        for b in BANNED:
            if b in low: errs.append(f"{path}: banned phrase '{b}'")
        is_example = path.endswith(".example") and low.startswith("example")
        if is_example:
            continue
        for tok in NUM.findall(s):
            if norm(tok) not in ok:
                errs.append(f"{path}: number '{tok}' is not in facts.yaml")
    return errs


if __name__ == "__main__":
    import json, sys
    for p in sys.argv[1:]:
        e = check(json.load(open(p)))
        print(p, "OK" if not e else e)
