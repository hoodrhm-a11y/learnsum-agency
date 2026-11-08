"""Connection check: confirms the Page token works and warns before data access expires.

Writes state/check.md and exits 1 if something needs attention (so GitHub opens an alert issue).
"""
import datetime as dt, os, sys
from publish import meta

WARN_DAYS = 14


def main():
    lines, bad = ["## LearnSum connection check", ""], False
    if not (meta.PAGE and meta.TOKEN):
        print("META_PAGE_ID / META_PAGE_TOKEN not set"); sys.exit(1)
    try:
        page = meta.get(meta.PAGE, fields="name,followers_count,fan_count")
        lines.append(f"✅ Connected to **{page.get('name')}** — followers: {page.get('followers_count', page.get('fan_count', 0))}")
    except meta.MetaError as e:
        lines.append(f"❌ Could not reach the Page: {e}"); bad = True
    try:
        info = meta.get("debug_token", input_token=meta.TOKEN).get("data", {})
        lines.append(f"✅ Using a {info.get('type', '?').lower()} token" + (" (fetched from your user key)" if meta.TOKEN != meta.USER_OR_PAGE_TOKEN else ""))
        exp = info.get("expires_at", 0)
        lines.append("✅ Token never expires" if not exp else f"⚠️ Token expires {dt.datetime.utcfromtimestamp(exp):%Y-%m-%d}")
        dax = info.get("data_access_expires_at")
        if dax:
            when = dt.datetime.fromtimestamp(dax, dt.timezone.utc)
            days = (when - dt.datetime.now(dt.timezone.utc)).days
            if days <= WARN_DAYS:
                bad = True
                lines.append(f"⚠️ **Data access expires in {days} days ({when:%b %d}).** Comments and views will stop until you "
                             "refresh it: Graph API Explorer → Generate Access Token → then repeat the Page token steps and "
                             "update the META_PAGE_TOKEN secret.")
            else:
                lines.append(f"✅ Data access good until {when:%b %d, %Y} ({days} days)")
        scopes = set(info.get("scopes", []))
        need = {"pages_manage_posts", "pages_manage_engagement", "pages_read_engagement"}
        missing = need - scopes
        if missing:
            bad = True; lines.append(f"❌ Missing permissions: {', '.join(sorted(missing))}")
        else:
            lines.append("✅ Posting and comment permissions present")
        if "pages_read_user_content" not in scopes:
            lines.append("ℹ️ pages_read_user_content isn't granted (Meta doesn't offer it to this app); comment reading uses pages_read_engagement.")
    except meta.MetaError as e:
        lines.append(f"⚠️ Could not inspect the token: {e}")
    os.makedirs("state", exist_ok=True)
    open("state/check.md", "w").write("\n".join(lines))
    print("\n".join(lines))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
