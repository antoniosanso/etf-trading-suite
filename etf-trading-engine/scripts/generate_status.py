#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_status.py — Combine universe + KPI into a single status.json
"""
import json, argparse, os

def safe_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe-json", default="outputs/universe/universe_snapshot.json")
    ap.add_argument("--kpi-json", default="outputs/status_kpi.json")
    ap.add_argument("--out", default="outputs/status.json")
    args = ap.parse_args()

    uni = safe_json(args.universe_json)
    kpi = safe_json(args.kpi_json)

    status = {
        "schema": 2,
        "universe": {
            "total_rows": uni.get("total_rows"),
            "unique_tickers": uni.get("unique_tickers"),
            "duplicate_rows": uni.get("duplicate_rows"),
        },
        "kpi": kpi or {},
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
