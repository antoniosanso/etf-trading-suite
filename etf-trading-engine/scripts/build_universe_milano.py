#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, time, json
import pandas as pd
import requests
try:
    import yfinance as yf
except Exception as e:
    print("[FATAL] yfinance not available:", e, file=sys.stderr)
    sys.exit(1)

WL_PATH  = "etf-trading-config/whitelist_symbols_mi.txt"
OUT_CSV  = "etf-trading-config/universe.csv"
DIAG_TXT = "etf-trading-config/universe_diagnostics.txt"

THEME_QUERIES = [
    "ETF Technology","ETF Information Technology","ETF Semiconductor","ETF Robotics",
    "ETF Automation","ETF Artificial Intelligence","ETF Big Data","ETF Cybersecurity",
    "ETF Cloud","ETF Software","ETF Digital","ETF Biotechnology","ETF Healthcare",
    "ETF Clean Energy","ETF Battery","ETF Defence","ETF Aerospace","ETF Luxury",
    "ETF Payments","ETF FinTech","ETF Nasdaq","ETF S&P 500","ETF MSCI USA",
    "ETF MSCI World","ETF Europe Technology","ETF Robotics AI"
]

def read_whitelist():
    if not os.path.exists(WL_PATH): return []
    with open(WL_PATH) as f:
        lines = [l.strip() for l in f if l.strip().endswith(".MI")]
    return list(dict.fromkeys(lines))

def validate(symbols):
    keep, bad = [], {}
    for s in symbols:
        try:
            tk = yf.Ticker(s)
            h = tk.history(period="1y", auto_adjust=True)
            if h is None or h.empty or len(h.dropna()) < 10:
                bad[s] = "no_history"; continue
            keep.append(s)
        except Exception as e:
            bad[s] = str(e)
        time.sleep(0.02)
    return keep, bad

def yahoo_candidates(limit=400):
    base = "https://query1.finance.yahoo.com/v1/finance/search"
    headers = {"User-Agent":"Mozilla/5.0"}
    out = []
    for q in THEME_QUERIES:
        try:
            r = requests.get(base, params={"q": q, "lang":"it-IT", "quotesCount":100},
                             headers=headers, timeout=15)
            for it in r.json().get("quotes", []):
                sym = it.get("symbol","")
                if sym.endswith(".MI") and "ETF" in (it.get("longname","")+it.get("shortname","")).upper():
                    out.append(sym)
        except Exception: pass
        time.sleep(0.05)
    return list(dict.fromkeys(out))[:limit]

def main():
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    wl = read_whitelist()
    keep, bad = validate(wl)
    if len(keep) < 50:
        cand = yahoo_candidates()
        add, bad2 = validate([c for c in cand if c not in keep])
        keep.extend(add)
        bad.update(bad2)
    keep = list(dict.fromkeys(keep))[:50]
    rows = []
    for s in keep:
        rows.append({"symbol_yf": s, "isin": "", "name": s,
                     "exchange_currency": "EUR", "listing": "BorsaItaliana"})
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    with open(DIAG_TXT,"w") as f: json.dump(bad,f,indent=2)
    print(f"[OK] Universe built with {len(rows)} ETFs (EUR, Milano).")

if __name__=="__main__": main()
