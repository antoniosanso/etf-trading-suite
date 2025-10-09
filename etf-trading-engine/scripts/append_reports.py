#!/usr/bin/env python3
import json, datetime
from pathlib import Path

Path("reports/history").mkdir(parents=True, exist_ok=True)
Path("reports/daily").mkdir(parents=True, exist_ok=True)
ts = datetime.datetime.utcnow().isoformat()+"Z"

def loadj(p):
    try:
        return json.load(open(p,"r",encoding="utf-8"))
    except Exception:
        return {}

k = loadj("outputs/kpis.json")
wf = loadj("outputs/wf_report.json")
gr = loadj("outputs/guardrails_status.json")

# daily snapshot
today = datetime.date.today().isoformat()
Path(f"reports/daily/{today}").mkdir(parents=True, exist_ok=True)
for src in ("kpis.json","wf_report.json","guardrails_status.json"):
    try:
        Path(f"reports/daily/{today}/{src}").write_text(open(f"outputs/{src}",'r',encoding='utf-8').read(), encoding='utf-8')
    except Exception:
        pass

# jsonl histories
with open("reports/history/kpis.jsonl","a",encoding="utf-8") as f:
    f.write(json.dumps({"ts":ts,"kpis":k})+"\n")
with open("reports/history/wf.jsonl","a",encoding="utf-8") as f:
    f.write(json.dumps({"ts":ts,"wf":wf})+"\n")

# latest
json.dump({"ts":ts,"kpis":k,"wf":wf,"guardrails":gr}, open("reports/latest.json","w",encoding="utf-8"), indent=2)
print("[OK] reports updated")
