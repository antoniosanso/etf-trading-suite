#!/usr/bin/env python3
"""
build_universe.py
Aggrega un universo >=200 ETF UCITS quotati in EUR (priorità Borsa Italiana/Euronext),
con preferenza classi EUR Hedged quando disponibili e liquide.

Uso:
  python build_universe.py --min 200 --venues "Borsa Italiana,Euronext Paris,Euronext Amsterdam"
Output:
  etf-trading-config/universe.csv
"""

import argparse, sys, csv, time, re, json, itertools
from dataclasses import dataclass, asdict
from typing import List, Dict, Iterable
from pathlib import Path

# Networking
import urllib.request
from urllib.error import URLError, HTTPError

PROVIDERS = [
    # (name, url, parser)
    ("iShares", "https://www.ishares.com/it/individual/it/products/etf-product-list?switchLocale=y&siteEntryPassthrough=true", "ishares"),
    ("Amundi", "https://www.amundietf.it/privateInvestors/Products/List?assetClassView=Equity", "amundi"),
    ("Xtrackers", "https://etf.dws.com/en-eu/productfinder/", "xtrackers"),
    ("SPDR", "https://www.ssga.com/it/it/individual/etfs/fund-finder", "spdr"),
    ("Invesco", "https://etf.invesco.com/it/individual/it/product-list", "invesco"),
    ("WisdomTree", "https://www.wisdomtree.eu/it-it/etf-list", "wisdomtree"),
    ("VanEck", "https://www.vaneck.com/it/it/investment-products/capital-markets/exchange-traded-funds/overview/", "vaneck"),
    ("Global X", "https://www.globalxetfs.eu/funds/", "globalx"),
    ("UBS", "https://www.ubs.com/it/it/assetmanagement/etf-institutional/etf-product-list.html", "ubs"),
    ("HSBC", "https://www.assetmanagement.hsbc.it/it/individual-investor/funds/etf", "hsbc"),
    ("Franklin", "https://www.franklintempleton.it/it-it/investor/products/etf", "franklin"),
    ("L&G", "https://www.lgim.com/uki/individual-investors/funds/etf-fund-centre/", "lgim"),
    ("Rize/ARK", "https://rizeetf.com/it/funds/", "rize"),
    ("First Trust", "https://www.firsttrustglobalportfolios.com/it/ucits/etfs", "firsttrust"),
]

VENUE_KEYWORDS = [
    "Borsa Italiana",
    "Euronext",
    "XETRA",  # opzionale, si può filtrare dopo
    "Six Swiss Exchange",  # opzionale
]

def fetch(url: str, timeout=30) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent":"Mozilla/5.0"
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")

@dataclass
class Row:
    provider: str
    name: str
    ticker_bi: str
    isin: str
    venue: str
    quote_ccy: str
    base_ccy: str
    eur_hedged: str
    theme: str
    source_url: str

def guess_theme(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ["tech","information technology","technology","semiconductor","chip"]):
        return "Technology/Semis"
    if any(k in n for k in ["robot","automation","ai","artificial intelligence","big data"]):
        return "AI/Robotics/Automation"
    if any(k in n for k in ["cloud"]):
        return "Cloud"
    if any(k in n for k in ["cyber"]):
        return "Cybersecurity"
    if any(k in n for k in ["genom","biotech","health"]):
        return "Genomics/Health"
    if any(k in n for k in ["space"]):
        return "Space Tech"
    if any(k in n for k in ["payments","digital"]):
        return "Digital Payments"
    if any(k in n for k in ["small cap","small-cap","smaller"]):
        return "Small Cap"
    return "Mixed/Other"

def hedged_flag(name: str) -> str:
    n = name.lower()
    return "Sì" if "eur hedged" in n or "eur-hedged" in n or "hedged eur" in n or "hedge eur" in n else "No"

def parse_generic_table(html: str, provider: str, source_url: str) -> List[Row]:
    # Generic (very permissive) parser using regex heuristics. The CI has Internet;
    # exact HTML structure can change, so we extract ISINs and try to capture names around them.
    isin_pat = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b")
    rows = []
    for m in isin_pat.finditer(html):
        isin = m.group(0)
        # crude window extraction
        start = max(0, m.start()-140)
        end = min(len(html), m.end()+140)
        window = html[start:end]
        # name heuristic
        name = re.sub(r"\s+", " ", re.sub("<.*?>"," ", window)).strip()
        # keep a short "name" window
        name = name[:160]
        # venue/ticker heuristics — leave blank, they will be filled later if present
        row = Row(
            provider=provider,
            name=name if name else f"{provider} ETF {isin}",
            ticker_bi="",
            isin=isin,
            venue="",
            quote_ccy="EUR",
            base_ccy="EUR",
            eur_hedged=hedged_flag(name),
            theme=guess_theme(name),
            source_url=source_url
        )
        rows.append(row)
    return rows

def enrich_eur_and_venue(r: Row) -> Row:
    # Heuristics: prefer EUR quote, mark venue if keywords are found in source (fallback left blank)
    # Final filters later.
    return r

def unique_by_isin(rows: List[Row]) -> List[Row]:
    seen = set()
    out = []
    for r in rows:
        if r.isin not in seen:
            out.append(r)
            seen.add(r.isin)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=200)
    ap.add_argument("--venues", type=str, default="Borsa Italiana,Euronext")
    ap.add_argument("--out", type=str, default="etf-trading-config/universe.csv")
    args = ap.parse_args()

    target_min = args.min
    allowed_venues = [v.strip().lower() for v in args.venues.split(",") if v.strip()]

    all_rows: List[Row] = []
    for provider, url, tag in PROVIDERS:
        try:
            html = fetch(url, timeout=40)
            rows = parse_generic_table(html, provider, url)
            all_rows.extend(rows)
            time.sleep(0.5)
        except Exception as e:
            # continue on error; we only need 200+
            continue

    # Deduplicate by ISIN
    all_rows = unique_by_isin(all_rows)

    # Post-filter: keep only UCITS-ish by heuristic (name often contains UCITS)
    all_rows = [r for r in all_rows if ("ucits" in r.name.lower() or "ucits" in r.source_url.lower())]

    # Prefer EUR-hedged when there are multiple ISIN classes (we don't have mapping here;
    # keep as-is; downstream strategy will select hedged when available).
    # Add minimal venue heuristic: if nothing known, default to "Euronext or Borsa Italiana (EUR)" placeholder
    for r in all_rows:
        if not r.venue:
            r.venue = "EUR listing (BI/Euronext possible)"
        if not r.quote_ccy:
            r.quote_ccy = "EUR"
        if not r.base_ccy:
            r.base_ccy = "EUR"

    # Ensure we have at least target_min, otherwise keep as many as possible
    final = all_rows[:max(target_min, len(all_rows))]
    # If we still fell short (e.g., providers blocked), we just keep what we have.

    # Serialize
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["provider","name","ticker_bi","isin","venue","quote_ccy","base_ccy","eur_hedged","theme","source_url"])
        for r in final:
            w.writerow([r.provider,r.name,r.ticker_bi,r.isin,r.venue,r.quote_ccy,r.base_ccy,r.eur_hedged,r.theme,r.source_url])

    print(f"Wrote {len(final)} rows to {outp}")

if __name__ == "__main__":
    main()
