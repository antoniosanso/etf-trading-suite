#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kpi_aggregator.py — Consolidate KPIs from known locations if present.
Looks for:
- outputs/backtest/kpis.json
- outputs/wf/wf_report.json
- outputs/wf/wf_summary.txt
Produces:
- outputs/status_kpi.json  (gracefully degrades if files not found)
"""
import os, json, argparse

def safe_read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", default="outputs/backtest/kpis.json")
    ap.add_argument("--wf", default="outputs/wf/wf_report.json")
    ap.add_argument("--out", default="outputs/status_kpi.json")
    args = ap.parse_args()

    kpis = safe_read_json(args.backtest) or {}
    wf   = safe_read_json(args.wf) or {}

    # Minimal set expected by your guardrails (if present)
    payload = {
        "kpis": {
            "sharpe": kpis.get("sharpe"),
            "profit_factor": kpis.get("profit_factor"),
            "max_drawdown": kpis.get("max_dd"),
        },
        "walk_forward": {
            "calmar_cov": wf.get("calmar_cov"),
            "windows": wf.get("windows"),
        },
        "present": {
            "kpis": bool(kpis),
            "wf": bool(wf),
        }
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
