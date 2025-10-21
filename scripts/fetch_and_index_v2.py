#!/usr/bin/env python3
import argparse, os, time, json
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf
from pandas_datareader import data as pdr

SAFE_SEED = [
    "CSPX.L","VUAA.AS","VWCE.DE","EUNL.DE","SXR8.DE","SPY5.L","IS3N.DE","IUSQ.DE","IUS3.DE","IUSP.L",
    "EQQQ.L","XDJP.DE","XD9U.DE","XDWD.DE","XESC.DE","XDEV.DE",
    "EMIM.L","EIMI.L","IGLT.L","IEMB.L",
    "EFA","EEM","EWJ","EWH","EWA","EWG","EWC","EWU","AGG","BND","EMB","BIL",
]

ALT_SUFFIXES = [".DE",".L",".AS",".PA",".SW",".IR",".BR", ".MI"]

def load_universe(path):
    want = set()
    p = Path(path)
    if p.exists():
        try:
            df = pd.read_csv(p)
            cols = {c.lower(): c for c in df.columns}
            for k in ["ticker_bi","ticker","symbol"]:
                if k in cols:
                    want |= {str(t).strip() for t in df[cols[k]].dropna() if str(t).strip()}
                    break
        except Exception:
            pass
    return want

def expand_symbols(symbols):
    out = set()
    for s in symbols:
        if not s:
            continue

        # Se il ticker è già con suffisso, lascialo stare
        if "." in s:
            out.add(s)
            continue

        # Alcuni ETF americani noti NON hanno equivalenti europei
        if s in ["AGG", "BND", "EFA", "EEM", "EWJ", "EWA", "EWG", "EWC", "EWU"]:
            out.add(s)
            continue

        # Altri simboli europei: prova solo i mercati più comuni
        for suf in [".L", ".DE", ".AS", ".MI"]:
            out.add(s + suf)

    return out

def fetch_yf(sym):
    try:
        df = yf.download(sym, period="max", interval="1d", progress=False, auto_adjust=False)
        if df is None or df.empty:
            return None
        df = df.reset_index().rename(columns={
            "Date":"Date","Open":"Open","High":"High","Low":"Low",
            "Close":"Close","Adj Close":"AdjClose","Volume":"Volume"
        })
        df["Ticker"] = sym
        if "Currency" not in df.columns:
            df["Currency"] = ""
        cols = ["Date","Ticker","Open","High","Low","Close","Volume","Currency"]
        for c in cols:
            if c not in df.columns:
                df[c] = np.nan
        return df[cols]
    except Exception:
        return None

def fetch_stooq(sym):
    base = sym.split(".")[0]
    try:
        df = pdr.DataReader(base, "stooq")
        if df is None or df.empty:
            return None
        df = df.sort_index().reset_index().rename(columns={
            "Date":"Date","Open":"Open","High":"High","Low":"Low",
            "Close":"Close","Volume":"Volume"
        })
        df["Ticker"] = sym
        df["Currency"] = ""
        return df[["Date","Ticker","Open","High","Low","Close","Volume","Currency"]]
    except Exception:
        return None

def cross_check(a, b, tol=0.8):
    try:
        if a is None or b is None or a.empty or b.empty:
            return True
        a = a.copy(); b = b.copy()
        a["Date"] = pd.to_datetime(a["Date"], errors="coerce"); a = a.dropna(subset=["Date"])
        b["Date"] = pd.to_datetime(b["Date"], errors="coerce"); b = b.dropna(subset=["Date"])
        if a.empty or b.empty:
            return True
        d = min(a["Date"].max(), b["Date"].max())
        a_last = float(a[a["Date"]==d]["Close"].iloc[-1]) if (a["Date"]==d).any() else None
        b_last = float(b[b["Date"]==d]["Close"].iloc[-1]) if (b["Date"]==d).any() else None
        if a_last is None or b_last is None:
            return True
        diff = abs(a_last - b_last) / max(1e-9, b_last) * 100.0
        return diff <= tol
    except Exception:
        return True

def normalize_numeric(df):
    # se le colonne sono multi-index, riducile a stringhe semplici
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join([str(x) for x in tup if x]) for tup in df.columns]
    else:
        df.columns = [str(c).strip().capitalize() for c in df.columns]

    # assicurati che ci siano almeno queste colonne
    for col in ["Date", "Close"]:
        if col not in df.columns:
            df[col] = np.nan

    # conversione sicura a numerico
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            try:
                vals = pd.Series(df[col].values.flatten())
                df[col] = pd.to_numeric(vals, errors="coerce")
            except Exception:
                df[col] = np.nan

    # parsing date robusto
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"])

    return df

def build_index_and_latest(root, latest_dir):
    files = sorted(Path(root).glob("*.csv"))
    items, latest = [], []
    for p in files:
        try:
            df = pd.read_csv(p, parse_dates=["Date"])
            if df.empty:
                continue
            df = df.sort_values("Date")
            last = df.iloc[-1]
            latest.append({
                "Date": last["Date"],
                "Ticker": last.get("Ticker", p.stem),
                "Open": last.get("Open"), "High": last.get("High"),
                "Low": last.get("Low"), "Close": last.get("Close"),
                "Volume": last.get("Volume"), "Currency": last.get("Currency","")
            })
            items.append({
                "ticker": str(last.get("Ticker", p.stem)),
                "path": f"data/{p.name}",
                "last_date": str(pd.to_datetime(last["Date"]).date()),
                "rows": int(df.shape[0]),
                "bytes": p.stat().st_size
            })
        except Exception:
            continue
    Path(latest_dir, "index.json").write_text(
        json.dumps({"count": len(items), "generated_utc": pd.Timestamp.utcnow().isoformat(), "items": items},
                   ensure_ascii=False, separators=(",",":")),
        encoding="utf-8"
    )
    if latest:
        pd.DataFrame(latest, columns=["Date","Ticker","Open","High","Low","Close","Volume","Currency"])\
          .to_csv(Path(latest_dir, "eod-latest.csv"), index=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="")
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--latest-dir", required=True)
    ap.add_argument("--min", type=int, default=220)
    ap.add_argument("--tolerance", type=float, default=0.8)
    args = ap.parse_args()

    Path(args.data_root).mkdir(parents=True, exist_ok=True)
    Path(args.latest_dir).mkdir(parents=True, exist_ok=True)

    want = set(SAFE_SEED)
    want |= load_universe(args.universe)
    want = expand_symbols(want)

    existing = {p.stem for p in Path(args.data_root).glob("*.csv")}
    to_fetch = [s for s in sorted(want) if s not in existing]

    added = 0
    for sym in to_fetch:
        yf_df = fetch_yf(sym)
        stq_df = fetch_stooq(sym)
        ok = cross_check(yf_df, stq_df, args.tolerance)
        out = yf_df if (yf_df is not None and ok) else (stq_df if stq_df is not None else None)
        if out is None:
            continue
        out = normalize_numeric(out)
        if out.shape[0] < 50:  # evita serie troppo corte
            continue
        out.to_csv(Path(args.data_root, f"{sym}.csv"), index=False)
        added += 1
        if (len(existing) + added) >= args.min:
            break
        time.sleep(0.2)

    build_index_and_latest(args.data_root, args.latest_dir)

if __name__ == "__main__":
    main()
