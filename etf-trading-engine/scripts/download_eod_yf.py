#!/usr/bin/env python3
import pandas as pd, yfinance as yf
from pathlib import Path
OUT = Path("data/eod"); OUT.mkdir(parents=True, exist_ok=True)
u = pd.read_csv("etf-trading-config/universe.csv")
ok=0
for s in u["symbol_yf"].dropna().unique():
    d = yf.download(s, period="5y", auto_adjust=True, threads=False)
    if d is None or d.empty or len(d.dropna())<10:
        print(f"[WARN] {s} skipped"); continue
    d.to_csv(OUT/f"{s}.csv"); ok+=1
print(f"[OK] Downloaded {ok} files")
