#!/usr/bin/env python3
import argparse, os
from pathlib import Path
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)   # per-ticker CSV: data/*.csv
    ap.add_argument("--out-dir", required=True)     # latest/
    args = ap.parse_args()

    data_root = Path(args.data_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted([p for p in data_root.glob("*.csv") if p.is_file()])
    # files.txt
    with (out_dir / "files.txt").open("w", encoding="utf-8") as f:
        for p in files:
            rel = p.as_posix().split("etf-datalake/")[-1] if "etf-datalake/" in p.as_posix() else p.as_posix()
            f.write(rel + "\n")

    # manifest.csv and eod-latest.csv
    manifest_rows = []
    latest_rows = []
    for p in files:
        ticker = p.stem
        try:
            df = pd.read_csv(p, parse_dates=["Date"])
            if "Date" not in df.columns:
                continue
            df = df.sort_values("Date")
            last = df.iloc[-1:].copy()
            # normalize columns
            for col in ["Open","High","Low","Close","Volume","Currency","Ticker"]:
                if col not in last.columns:
                    last[col] = None
            last["Ticker"] = ticker
            latest_rows.append(last[["Date","Ticker","Open","High","Low","Close","Volume","Currency"]].iloc[0].to_dict())

            last_date = pd.to_datetime(df["Date"].max()).date().isoformat() if not df.empty else ""
            manifest_rows.append({
                "path": p.as_posix().split("etf-datalake/")[-1] if "etf-datalake/" in p.as_posix() else p.as_posix(),
                "ticker": ticker,
                "last_date": last_date,
                "rows": int(df.shape[0]),
                "size_bytes": p.stat().st_size
            })
        except Exception:
            manifest_rows.append({
                "path": p.as_posix().split("etf-datalake/")[-1] if "etf-datalake/" in p.as_posix() else p.as_posix(),
                "ticker": ticker,
                "last_date": "",
                "rows": 0,
                "size_bytes": p.stat().st_size
            })

    if manifest_rows:
        pd.DataFrame(manifest_rows, columns=["path","ticker","last_date","rows","size_bytes"]).to_csv(out_dir / "manifest.csv", index=False)
    if latest_rows:
        pd.DataFrame(latest_rows, columns=["Date","Ticker","Open","High","Low","Close","Volume","Currency"]).to_csv(out_dir / "eod-latest.csv", index=False)

if __name__ == "__main__":
    main()
