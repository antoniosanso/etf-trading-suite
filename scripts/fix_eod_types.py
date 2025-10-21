#!/usr/bin/env python3
import argparse
import pandas as pd
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.snapshot)

    # forza i tipi numerici per evitare TypeError su operazioni tra stringhe
    for c in ["Open","High","Low","Close","Volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date

    df = df.dropna(subset=["Date","Ticker","Close"])

    Path(Path(args.output).parent).mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

if __name__ == "__main__":
    main()
