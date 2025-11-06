#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf
from pathlib import Path

UNIVERSE = Path("etf-trading-config/universe.csv")
OUTDIR = Path("data/eod")

def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    u = pd.read_csv(UNIVERSE)
    ok = 0
    for symbol in u["symbol_yf"].dropna().unique():
        data = yf.download(symbol, period="5y", auto_adjust=True, threads=False)
        if data is None or data.empty or len(data.dropna()) < 10:
            print(f"[WARN] {symbol}: no usable data from YF → SKIP")
            continue
        data.to_csv(OUTDIR / f"{symbol}.csv")
        ok += 1
    print(f"[OK] Downloaded {ok} symbols to {OUTDIR}")

if __name__ == "__main__":
    main()
