#!/usr/bin/env python3
import argparse, os, csv
from pathlib import Path
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eod-root", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    eod = Path(args.eod_root)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = sorted([p for p in eod.glob("*/*.csv") if p.is_file()])
    # files.txt
    with (out / "files.txt").open("w", encoding="utf-8") as f:
        for p in files:
            f.write(p.as_posix().split("etf-datalake/")[-1] + "\n")

    rows = []
    for p in files:
        try:
            df = pd.read_csv(p, usecols=["Date","Ticker"], parse_dates=["Date"])
            last_date = df["Date"].max()
            ticker = df["Ticker"].dropna().unique()[0] if not df["Ticker"].dropna().empty else p.stem
            rows.append({
                "path": p.as_posix().split("etf-datalake/")[-1],
                "ticker": str(ticker),
                "last_date": last_date.date().isoformat() if pd.notna(last_date) else "",
                "rows": int(df.shape[0]),
                "size_bytes": p.stat().st_size
            })
        except Exception:
            rows.append({
                "path": p.as_posix().split("etf-datalake/")[-1],
                "ticker": p.stem,
                "last_date": "",
                "rows": 0,
                "size_bytes": p.stat().st_size
            })

    import pandas as pd
    pd.DataFrame(rows, columns=["path","ticker","last_date","rows","size_bytes"]).to_csv(out / "manifest.csv", index=False)

if __name__ == "__main__":
    main()
