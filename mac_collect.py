#!/usr/bin/env python3
"""Competitors Watch 2.0 - Mac collector (X + YouTube via Agent Reach). Read-only."""
import json, os, re, subprocess, datetime, urllib.request
from email.utils import parsedate_to_datetime

MAX_AGE = 3
LIMIT = 4000
TODAY = datetime.date.today()
X = {"Zerodha": ["zerodha"], "Groww": ["_groww", "TradeWithGroww_"], "Angel One": ["AngelOne"],
     "Upstox": ["upstox"], "Dhan": ["DhanHQ"], "ICICI Direct": ["icici_direct"], "INDmoney": ["INDmoneyApp"]}
YT = {"Zerodha": (["Zerodha", "Zerodha new feature"], ["Zerodha", "Varsity by Zerodha", "Markets by Zerodha"]),
      "Groww": (["Groww", "Groww new feature"], ["Groww", "Trading with Groww", "Mutual Funds at Groww"]),
      "Angel One": (["Angel One", "Angel One new feature"], ["Angel One"]),
      "Upstox": (["Upstox", "Upstox new feature"], ["Upstox"]),
      "Dhan": (["Dhan trading app", "Dhan new feature"], ["Dhan", "AI and Algos by Dhan"]),
      "ICICI Direct": (["ICICI Direct", "ICICI Direct new feature"], ["ICICI Direct"]),
      "INDmoney": (["INDmoney", "INDmoney new feature"], ["INDmoney"])}

def env():
    p = os.path.expanduser("~/.cw2_env")
    for line in open(p):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            os.environ[k] = v.strip().strip('"').strip("'")

def ar(args, timeout=120):
    try:
        out = subprocess.run(["agent-reach"] + args, capture_output=True, text=True, timeout=timeout)
        return json.loads(out.stdout)
    except Exception as e:
        return {"ok": False, "items": [], "error": {"message": str(e)}}

def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def trim(it):
    for k in ("text", "description"):
        if isinstance(it.get(k), str) and len(it[k]) > LIMIT:
            it[k] = it[k][:LIMIT] + " ...[trimmed]"
    return it

def age(s):
    if not s: return None
    try: d = parsedate_to_datetime(s).date()
    except Exception:
        try: d = datetime.date.fromisoformat(s[:10])
        except Exception: return None
    return (TODAY - d).days

env()
res = {"date": f"{TODAY}-mac", "source": "agent-reach-mac", "x": {}, "youtube": {}}
ok = n = 0

for co, handles in X.items():
    posts, errs = [], []
    for h in handles:
        r = ar(["twitter", "tweets", h, "--limit", "10"]); n += 1
        if r.get("ok"): ok += 1
        else: errs.append(str((r.get("error") or {}).get("code") or (r.get("error") or {}).get("message"))[:100])
        for it in r.get("items") or []:
            a = age(it.get("published_at"))
            if a is not None and a <= MAX_AGE:
                it["is_retweet"] = (it.get("text") or "").startswith("RT @")
                posts.append(trim(it))
    res["x"][co] = {"posts": posts, "errors": errs}

for co, (queries, chans) in YT.items():
    allowed = {norm(c) for c in chans}
    seen, cand = set(), []
    for q in queries:
        r = ar(["youtube", "search", q, "--limit", "10"]); n += 1
        if r.get("ok"): ok += 1
        for it in r.get("items") or []:
            u = it.get("url")
            if not u or "watch?v=" not in u or u in seen: continue
            seen.add(u)
            if not it.get("author") or norm(it["author"]) in allowed:
                cand.append(it)
    fresh, old, errs = [], 0, {}
    for it in cand[:10]:
        d = ar(["youtube", "read", it["url"]]); n += 1
        items = d.get("items") or []
        if d.get("ok") and items:
            ok += 1; v = items[0]
            if norm(v.get("author")) not in allowed: continue
            a = age(v.get("published_at"))
            if a is not None and a <= MAX_AGE: fresh.append(trim(v))
            else: old += 1
        else:
            m = str((d.get("error") or {}).get("code") or "unknown"); errs[m] = errs.get(m, 0) + 1
    res["youtube"][co] = {"candidates": len(cand), "fresh": fresh, "older_than_window": old, "errors": errs}

res["status"] = f"{ok}/{n} fetches succeeded"
print(res["status"])
for co in X: print(f"X  {co}: posts_in_window={len(res['x'][co]['posts'])} errors={res['x'][co]['errors']}")
for co, y in res["youtube"].items(): print(f"YT {co}: fresh={len(y['fresh'])} old={y['older_than_window']} errors={y['errors']}")

req = urllib.request.Request(os.environ["APPS_SCRIPT_URL"],
    data=json.dumps({"token": os.environ["SHARED_TOKEN"], "payload": res}).encode(),
    headers={"Content-Type": "application/json"})
print("upload:", urllib.request.urlopen(req, timeout=60).status)
