#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etf-trading-engine/scripts/fetch_universe.py
Drop-in utility to fetch and validate the ETF universe from a public GitHub repo.
"""
import os, sys, csv, json, argparse
from typing import Optional, Tuple, List
import requests

def _build_raw_url(repo: str, path: str, ref: str = "refs/heads/main") -> str:
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"

def _fetch(url: str, token: Optional[str] = None) -> Tuple[int, bytes]:
    headers = {"User-Agent": "universe-fetcher/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=30)
    return r.status_code, r.content

def get_universe_text(repo: Optional[str], path: Optional[str], ref: str, raw_url: Optional[str]) -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip() or None
    if raw_url:
        code, content = _fetch(raw_url, token)
        if code == 200:
            return content.decode("utf-8", errors="replace")
        raise RuntimeError(f"fetch failed {code} for raw={raw_url}")
    if not (repo and path):
        raise ValueError("Either --raw or both --repo and --path must be provided.")
    url = _build_raw_url(repo, path, ref)
    code, content = _fetch(url, token)
    if code == 200:
        return content.decode("utf-8", errors="replace")
    # Fallback: GitHub Contents API (handles alt refs/default branches)
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}"
    code, content = _fetch(api_url, token)
    if code == 200:
        try:
            data = json.loads(content.decode("utf-8", errors="replace"))
            dl = data.get("download_url")
            if dl:
                code2, content2 = _fetch(dl, token)
                if code2 == 200:
                    return content2.decode("utf-8", errors="replace")
        except Exception:
            pass
    raise RuntimeError(f"Fetch failed for repo={repo}, path={path}, ref={ref} (last code {code}).")

def parse_universe_csv(text: str) -> List[str]:
    tickers: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            t = line.split(",")[0].strip()
            if t:
                tickers.append(t)
        else:
            tickers.append(line)
    return tickers

def write_snapshot(tickers: List[str], out_csv: str, out_json: str):
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for t in tickers:
            w.writerow([t])
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "total_rows": len(tickers),
            "unique_tickers": len(list(dict.fromkeys(tickers))),
            "duplicate_rows": len(tickers) - len(list(dict.fromkeys(tickers))),
            "tickers": list(dict.fromkeys(tickers))
        }, f, ensure_ascii=False, indent=2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="antoniosanso/etf-trading-suite")
    ap.add_argument("--path", default="etf-trading-config/universe.csv")
    ap.add_argument("--ref", default="refs/heads/main")
    ap.add_argument("--raw", default=None)
    ap.add_argument("--outdir", default="outputs/universe")
    args = ap.parse_args()

    text = get_universe_text(args.repo, args.path, args.ref, args.raw)
    tickers = parse_universe_csv(text)

    out_csv = os.path.join(args.outdir, "universe_snapshot.csv")
    out_json = os.path.join(args.outdir, "universe_snapshot.json")
    write_snapshot(tickers, out_csv, out_json)

    # Human log
    uniq = list(dict.fromkeys(tickers))
    dup = len(tickers) - len(uniq)
    print("Universe summary")
    print("----------------")
    print(f"Total rows     : {len(tickers)}")
    print(f"Unique tickers : {len(uniq)}")
    print(f"Duplicate rows : {dup}")
    sample = ", ".join(uniq[:10])
    if sample:
        print(f"Sample         : {sample}{' ...' if len(uniq)>10 else ''}")

if __name__ == "__main__":
    main()
