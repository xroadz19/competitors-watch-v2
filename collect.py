import json, subprocess, os, urllib.request, datetime

cfg = json.load(open("config.json"))

def run(args):
    try:
        out = subprocess.run(["agent-reach"] + args, capture_output=True, text=True, timeout=180)
        return json.loads(out.stdout)
    except Exception as e:
        return {"ok": False, "items": [], "error": {"message": str(e)}}

result = {"date": datetime.date.today().isoformat(), "youtube": {}, "press": {}}
for q in cfg["youtube_queries"]:
    result["youtube"][q] = run(["youtube", "search", q, "--limit", "3"])
for url in cfg["press_pages"]:
    result["press"][url] = run(["read", url])

ok = sum(1 for g in ("youtube", "press") for r in result[g].values() if r.get("ok"))
total = sum(len(result[g]) for g in ("youtube", "press"))
result["status"] = f"{ok}/{total} fetches succeeded"
print(result["status"])

req = urllib.request.Request(
    os.environ["APPS_SCRIPT_URL"],
    data=json.dumps({"token": os.environ["SHARED_TOKEN"], "payload": result}).encode(),
    headers={"Content-Type": "application/json"},
)
print(urllib.request.urlopen(req, timeout=60).status)
