#!/usr/bin/env python3
"""Competitors Watch 2.0 - Mac collector v2: same sources as the live flow. Read-only."""
import json, os, re, shutil, subprocess, datetime, time, urllib.request
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
NOW = datetime.datetime.now(IST)
END = NOW.replace(hour=6, minute=0, second=0, microsecond=0)
if NOW < END: END -= datetime.timedelta(days=1)
START = END - datetime.timedelta(days=1)
TODAY = NOW.date()
LIMIT = 4000

X = {
 "Zerodha": ["zerodha","zerodhamarkets","ZerodhaVarsity","CoinByZerodha","nithin0dha","tradingqna","Zero1byZerodha","zerodhacapital","Rainmatterin","ZerodhaAMC","nikhilkamathcio","karthikrangappa","vishaljain2510","SubtextZerodha","zerodhaonline"],
 "Groww": ["_groww","Growwamcltd","TradeWithGroww_","lkeshre","_harshjain26","ishanishu"],
 "Angel One": ["AngelOne","AngelOneMF","ionicwealth","DineshThakkar","kenghe","nalinmoniz","abhymurarka","ankitapathak_"],
 "Upstox": ["upstox","UpstoxSupport","vyaditya"],
 "Dhan": ["DhanHQ","DhanCares","DhanLive","RaiseTheBarHQ","BeingPractical","JPGupta1"],
 "ICICI Direct": ["ICICI_Direct","ICICIDirectcare"],
 "INDmoney": ["INDmoneyApp","ashishkashyap","Nikhilbehl_"]}
YT = {
 "Zerodha": ["@zerodhaonline","@marketsbyzerodha","@varsitybyzerodha"],
 "Groww": ["@Groww","@TradingwithGroww","@MutualFundsAtGroww"],
 "Angel One": ["@angelone"], "Upstox": ["@UpstoxOfficial"],
 "Dhan": ["@DhanHQ","@AIandAlgosbyDhan"], "ICICI Direct": ["@ICICIDirectOfficial"], "INDmoney": ["@INDmoney"]}
BRANDS = {"Zerodha": "Zerodha OR Kite", "Groww": "Groww", "Angel One": '"Angel One"', "Upstox": "Upstox",
          "Dhan": "Dhan", "ICICI Direct": '"ICICI Direct" OR ICICIdirect', "INDmoney": "INDmoney OR INDstocks"}
COMPLAINT = '(issue OR glitch OR "not working" OR failed OR withdrawal OR scam OR complaint OR stuck OR down OR error)'

def env():
    for line in open(os.path.expanduser("~/.cw2_env")):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            os.environ[k] = v.strip().strip('"').strip("'")

def ar(args, timeout=120):
    try:
        out = subprocess.run(["agent-reach"] + args, capture_output=True, text=True, timeout=timeout)
        return json.loads(out.stdout)
    except Exception as e:
        return {"ok": False, "items": [], "error": {"message": str(e)[:120]}}

def err(r): 
    e = r.get("error") or {}
    return str(e.get("code") or e.get("message") or "unknown")[:100]

def arx(args):
    for i in range(3):
        r = ar(args, timeout=180)
        msg = str((r.get("error") or {}).get("message") or "")
        if r.get("ok"): break
        if "paused" in msg and i < 2:
            time.sleep(60); continue
        if err(r) == "TIMEOUT" and i < 1:
            time.sleep(20); continue
        break
    time.sleep(5)
    return r

def trim(it):
    for k in ("text", "description"):
        if isinstance(it.get(k), str) and len(it[k]) > LIMIT:
            it[k] = it[k][:LIMIT] + " ...[trimmed]"
    it.pop("raw", None)
    return it

def tdt(s):
    try: return parsedate_to_datetime(s).astimezone(IST)
    except Exception: return None

def in_window(s): 
    d = tdt(s)
    return d is not None and START <= d < END

def ytdlp():
    p = shutil.which("yt-dlp")
    if p: return p
    for c in ["~/.local/share/uv/tools/agent-reach/bin/yt-dlp"]:
        c = os.path.expanduser(c)
        if os.path.exists(c): return c
    return None

env()
res = {"date": f"{TODAY}-mac", "source": "agent-reach-mac-v2", "window": f"{START:%Y-%m-%d %H:%M} to {END:%Y-%m-%d %H:%M} IST", "x": {}, "youtube": {}, "mentions": {}}
ok = n = 0
print("window:", res["window"])

# 1) X: all handles the live flow uses
own = set()
for co, handles in X.items():
    posts, errs = [], []
    for h in handles:
        own.add(h.lower())
        r = arx(["twitter", "tweets", h, "--limit", "10"]); n += 1
        if r.get("ok"): ok += 1
        else: errs.append(f"{h}:{err(r)}")
        for it in r.get("items") or []:
            if in_window(it.get("published_at")):
                it["handle"] = h
                it["is_retweet"] = (it.get("text") or "").startswith("RT @")
                posts.append(trim(it))
    res["x"][co] = {"posts": posts, "errors": errs}
    print(f"X  {co}: posts={len(posts)} errors={errs[:3]}")

# 2) YouTube: list newest uploads per official channel (yt-dlp, Agent Reach's own YouTube engine), read each for date via Agent Reach
YD = ytdlp()
jobs = []
for co, chans in YT.items():
    res["youtube"][co] = {"fresh": [], "listed": 0, "older": 0, "errors": {}}
    for ch in chans:
        ids = []
        if not YD:
            res["youtube"][co]["errors"]["yt-dlp not found"] = 1; continue
        try:
            o = subprocess.run([YD, "--flat-playlist", "--playlist-end", "6", "-J", f"https://www.youtube.com/{ch}/videos"], capture_output=True, text=True, timeout=120)
            ids = [e["id"] for e in json.loads(o.stdout).get("entries", []) if e.get("id")]
        except Exception as e:
            res["youtube"][co]["errors"][f"list {ch}"] = 1
        res["youtube"][co]["listed"] += len(ids)
        jobs += [(co, f"https://www.youtube.com/watch?v={i}") for i in ids]

def read_one(job):
    return job[0], ar(["youtube", "read", job[1]])
with ThreadPoolExecutor(max_workers=4) as ex:
    for co, d in ex.map(read_one, jobs):
        n += 1
        y = res["youtube"][co]; items = d.get("items") or []
        if d.get("ok") and items:
            ok += 1; v = items[0]
            try: dt = datetime.date.fromisoformat((v.get("published_at") or "")[:10])
            except Exception: dt = None
            if dt and START.date() <= dt <= TODAY: y["fresh"].append(trim(v))
            else: y["older"] += 1
        else:
            m = err(d); y["errors"][m] = y["errors"].get(m, 0) + 1
for co, y in res["youtube"].items():
    print(f"YT {co}: listed={y['listed']} fresh={len(y['fresh'])} older={y['older']} errors={y['errors']}")

# 3) Customer mentions (last, so a failure here cannot affect the X step)
for co, q in BRANDS.items():
    r = arx(["twitter", "search", f"({q}) {COMPLAINT} since:{START:%Y-%m-%d}", "--limit", "20"]); n += 1
    if r.get("ok"): ok += 1
    hits = []
    for it in r.get("items") or []:
        if in_window(it.get("published_at")) and (it.get("author") or "").lower() not in own:
            hits.append(trim(it))
    res["mentions"][co] = {"posts": hits[:12], "error": None if r.get("ok") else err(r)}
    print(f"MENTIONS {co}: kept={len(hits)} error={res['mentions'][co]['error']}")

res["status"] = f"{ok}/{n} fetches succeeded"
print(res["status"])
req = urllib.request.Request(os.environ["APPS_SCRIPT_URL"],
    data=json.dumps({"token": os.environ["SHARED_TOKEN"], "payload": res}).encode(),
    headers={"Content-Type": "application/json"})
print("upload:", urllib.request.urlopen(req, timeout=60).status)
