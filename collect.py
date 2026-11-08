import json, subprocess, os, urllib.request, datetime, re

cfg = json.load(open("config.json"))
TODAY = datetime.date.today()
MAX_AGE = cfg.get("max_age_days", 3)
LIMIT = cfg.get("text_limit", 8000)


def ar(args, timeout=180):
    """Run one Agent Reach command and return its JSON, never raising."""
    try:
        out = subprocess.run(["agent-reach"] + args, capture_output=True, text=True, timeout=timeout)
        return json.loads(out.stdout)
    except Exception as e:
        return {"ok": False, "items": [], "error": {"message": str(e)}}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def trim(items):
    for it in items:
        for k in ("text", "description"):
            if isinstance(it.get(k), str) and len(it[k]) > LIMIT:
                it[k] = it[k][:LIMIT] + " ...[trimmed]"
    return items


def age_days(iso):
    try:
        return (TODAY - datetime.date.fromisoformat(iso[:10])).days
    except Exception:
        return None


result = {"date": TODAY.isoformat(), "source": "agent-reach", "youtube": {}, "press": {}}
fetches = ok = 0

# YouTube: search by company, keep only official channels, then read each video for its date.
for company, c in cfg["youtube"].items():
    allowed = {norm(x) for x in c["channels"]}
    seen, kept, dropped_authors, search_ok = set(), [], {}, False
    for q in c["queries"]:
        r = ar(["youtube", "search", q, "--limit", "10"])
        fetches += 1
        if r.get("ok"):
            ok += 1
            search_ok = True
        for it in r.get("items") or []:
            url = it.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            if norm(it.get("author")) in allowed:
                kept.append(it)
            else:
                a = it.get("author") or "?"
                dropped_authors[a] = dropped_authors.get(a, 0) + 1
    fresh, old = [], 0
    for it in kept[:8]:
        d = ar(["youtube", "read", it["url"]])
        fetches += 1
        items = d.get("items") or []
        if d.get("ok") and items:
            ok += 1
            v = items[0]
            a = age_days(v.get("published_at") or "")
            if a is not None and a <= MAX_AGE:
                fresh.append(trim([v])[0])
            else:
                old += 1
    result["youtube"][company] = {
        "search_ok": search_ok, "official_found": len(kept), "fresh": fresh,
        "older_than_window": old, "dropped_authors": dict(sorted(dropped_authors.items(), key=lambda x: -x[1])[:5]),
    }

# Press / exchange pages
for url in cfg["press_pages"]:
    r = ar(["read", url])
    fetches += 1
    if r.get("ok"):
        ok += 1
    r["items"] = trim(r.get("items") or [])
    result["press"][url] = r

result["status"] = f"{ok}/{fetches} fetches succeeded"
print(result["status"])
for company, y in result["youtube"].items():
    print(f"YT {company}: search_ok={y['search_ok']} official={y['official_found']} fresh={len(y['fresh'])} old={y['older_than_window']}")

req = urllib.request.Request(
    os.environ["APPS_SCRIPT_URL"],
    data=json.dumps({"token": os.environ["SHARED_TOKEN"], "payload": result}).encode(),
    headers={"Content-Type": "application/json"},
)
print(urllib.request.urlopen(req, timeout=60).status)
