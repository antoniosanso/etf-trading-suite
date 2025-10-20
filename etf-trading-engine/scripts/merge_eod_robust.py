#!/usr/bin/env python3
import argparse, sys, os, glob
import pandas as pd
from pathlib import Path

STD_COLS = ["Date","Ticker","Open","High","Low","Close","Volume","Currency"]

def find_sources(datalake_root: Path):
    # prefer per-ticker files in data/*.csv, else fallback to latest/eod-latest.csv
    data_dir = datalake_root / "data"
    latest_file = datalake_root / "latest" / "eod-latest.csv"
    files = sorted(data_dir.glob("*.csv"))
    if files:
        return ("files", files)
    if latest_file.exists():
        return ("latest", [latest_file])
    return (None, [])

def normalize_columns(df: pd.DataFrame):
    # map columns case-insensitively and with common aliases
    colmap = {c.lower(): c for c in df.columns}
    def pick(*names):
        for n in names:
            if n.lower() in colmap:
                return colmap[n.lower()]
        return None
    date = pick("Date","dt","date")
    ticker = pick("Ticker","ticker","Symbol","symbol")
    open_ = pick("Open","open")
    high = pick("High","high")
    low = pick("Low","low")
    close = pick("Close","close","Adj Close","adjclose","adj_close")
    vol = pick("Volume","volume")
    ccy = pick("Currency","currency","ccy")
    need = [date, ticker, open_, high, low, close, vol]
    if any(x is None for x in need):
        return None
    out = pd.DataFrame({
        "Date": pd.to_datetime(df[date]),
        "Ticker": df[ticker].astype(str),
        "Open": pd.to_numeric(df[open_], errors="coerce"),
        "High": pd.to_numeric(df[high], errors="coerce"),
        "Low": pd.to_numeric(df[low], errors="coerce"),
        "Close": pd.to_numeric(df[close], errors="coerce"),
        "Volume": pd.to_numeric(df[vol], errors="coerce"),
        "Currency": df[ccy] if ccy in df else ""
    })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datalake", required=True)   # path to ./etf-datalake
    ap.add_argument("--output", required=True)     # path to write merged csv
    args = ap.parse_args()

    root = Path(args.datalake)
    kind, sources = find_sources(root)
    if not sources:
        print("Nessun file valido trovato.", file=sys.stderr)
        sys.exit(1)

    dfs = []
    if kind == "files":
        for p in sources:
            try:
                df = pd.read_csv(p)
                df = normalize_columns(df)
                if df is not None and not df.empty:
                    dfs.append(df)
            except Exception:
                continue
    else:  # latest snapshot
        try:
            df = pd.read_csv(sources[0])
            df = normalize_columns(df)
            if df is not None and not df.empty:
                dfs.append(df)
        except Exception:
            pass

    if not dfs:
        print("Nessun file valido trovato.", file=sys.stderr)
        sys.exit(1)

    merged = pd.concat(dfs, ignore_index=True)
    merged = merged.dropna(subset=["Date","Ticker","Close"])
    merged = merged.sort_values(["Ticker","Date"])
    Path(Path(args.output).parent).mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output, index=False)

if __name__ == "__main__":
    main()
