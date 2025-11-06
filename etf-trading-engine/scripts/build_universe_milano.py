#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build a 50-ETF universe from Borsa Italiana (ETFPlus), prioritizing Tech/USA/Thematics,
validated on Yahoo Finance, all EUR listings on Milano.
Writes: etf-trading-config/universe.csv
"""
import re, time, sys
import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    import yfinance as yf
except Exception as e:
    print("[FATAL] yfinance not available:", e, file=sys.stderr)
    sys.exit(1)

THEMES = [
  "Technology","Information Technology","Semiconductor","Robotics","Automation","Artificial Intelligence",
  "Big Data","Cybersecurity","Cloud","Software","Digitalisation","Biotechnology","Healthcare Technology",
  "Clean Energy","Battery","Space","Defence","Aerospace","Luxury","Payments","FinTech","Blockchain"
]

def fetch_all_rows():
    base = "https://www.borsaitaliana.it/borsa/etf/tutti-gli-etf.html?isin=&from=1&to=99999&lang=it"
    html = requests.get(base, timeout=60).text
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    links = soup.select("a[href*='/borsa/etf/scheda/']")
    for a in links:
        url = "https://www.borsaitaliana.it" + a.get("href")
        try:
            t = requests.get(url, timeout=60).text
        except Exception:
            continue
        s = BeautifulSoup(t, "html.parser")
        head = s.select_one("h1")
        name = head.get_text(strip=True) if head else None
        isin = None
        for th in s.select("th"):
            if re.search("Isin", th.get_text(), re.I):
                td = th.find_next("td")
                if td:
                    isin = td.get_text(strip=True)
                    break
        ticker = None
        for th in s.select("th"):
            if re.search("Codice Alfanumerico", th.get_text(), re.I):
                td = th.find_next("td")
                if td:
                    ticker = td.get_text(strip=True).replace(" ", "")
                    break
        ccy = None
        for th in s.select("th"):
            if re.search("Valuta", th.get_text(), re.I):
                td = th.find_next("td")
                if td:
                    ccy = td.get_text(strip=True).upper()
                    break
        bench = None
        for th in s.select("th"):
            if re.search("Benchmark", th.get_text(), re.I):
                td = th.find_next("td")
                if td:
                    bench = td.get_text(" ", strip=True)
                    break
        if isin and ticker:
            rows.append({"name": name, "isin": isin, "ticker_bi": ticker, "ccy": ccy, "bench": bench})
        time.sleep(0.1)
    return pd.DataFrame(rows)

def validate_on_yahoo(symbols):
    keep = []
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period="1y", auto_adjust=True)
            if not hist.empty and len(hist.dropna()) >= 10:
                keep.append(sym)
        except Exception:
            pass
        time.sleep(0.05)
    return keep

def main():
    df = fetch_all_rows()
    df = df.dropna(subset=["isin","ticker_bi"]).copy()
    df["ticker_bi"] = df["ticker_bi"].str.replace(" ", "", regex=False)
    mask_theme = df["bench"].fillna("").str.contains("|".join(THEMES), case=False)
    uni = df[(df["ccy"]=="EUR") & (mask_theme)].copy()
    uni["symbol_yf"] = uni["ticker_bi"] + ".MI"
    # validate thematic first
    keep = set(validate_on_yahoo(list(uni["symbol_yf"])))
    # if < 50, expand with other EUR listings
    if len(keep) < 50:
        rest = df[(df["ccy"]=="EUR") & ~df["ticker_bi"].isin(uni["ticker_bi"])].copy()
        rest["symbol_yf"] = rest["ticker_bi"] + ".MI"
        extra = validate_on_yahoo([s for s in rest["symbol_yf"] if s not in keep])
        keep.update(extra[: max(0, 50 - len(keep)) ])
    final = df[df["ticker_bi"].add(".MI").isin(keep)].drop_duplicates(subset=["ticker_bi"]).copy()
    final["symbol_yf"] = final["ticker_bi"] + ".MI"
    out = final[["symbol_yf","isin","name"]].copy()
    out["exchange_currency"] = "EUR"
    out["listing"] = "BorsaItaliana"
    out = out.head(50)
    out.to_csv("etf-trading-config/universe.csv", index=False)
    print(f"[OK] Universe built with {len(out)} ETFs (EUR, Milano).")
    # also write diagnostics
    with open("etf-trading-config/universe_diagnostics.txt","w",encoding="utf-8") as f:
        f.write(out.to_string(index=False))

if __name__ == "__main__":
    main()
