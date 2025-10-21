#!/usr/bin/env python3
import argparse, os, sys, math, json, time
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
import yfinance as yf
from pandas_datareader import data as pdr

SEED_ETFS = {
    "CSPX.L","VUAA.AS","VWCE.DE","EUNL.DE","SXR8.DE","SXR8.MI","SPY5.L","IS3N.DE","IUSQ.DE","IUS3.DE","IUSP.L",
    "EQQQ.L","EXXT.DE","XDJP.DE","XD9U.DE","XDWD.DE","XDEM.MI","XRLU.MI","XESC.DE","XDEV.DE","XMME.MI","XMRM.MI",
    "EMIM.L","EIMI.L","SEME.MI","ESPO.MI","RBOT.MI","XAIX.MI","TNOW.MI","FRST.MI","WCLD.MI","WTAI.MI","CIBR.MI",
    "HACK.MI","BOTZ.MI","ROBO.MI","BATT.MI","WHEA.MI","GLUE.MI","EMQQ.MI","DPAY.MI","SEML.MI","WGLF.MI","CYBR.MI",
    "EFA","EEM","EWJ","EWH","EWA","EWG","EWC","EWU","AGG","BND","EMB","BIL"
}

def load_universe(path):
    want = set()
    p = Path(path)
    if p.exists():
        df = pd.read_csv(p)
        cols = {c.lower(): c for c in df.columns}
        cand = None
        for k in ["ticker_bi","ticker","symbol"]:
            if k in cols: cand = cols[k]; break
        if cand:
            want |= {str(t).strip() for t in df[cand].dropna() if str(t).strip()}
    return want

def expand_symbols(symbols):
    out = set()
    for s in symbols:
        if not s: continue
        if "." in s:
            out.add(s)
        else:
            for suf in [".MI",".AS",".PA",".DE"]:
                out.add(s + suf)
    return out

def ensure_dirs(data_root, latest_dir):
    Path(data_root).mkdir(parents=True, exist_ok=True)
    Path(latest_dir).mkdir(parents=True, exist_ok=True)

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
        if "Currency" not in df.columns: df["Currency"] = ""
        cols_full = ["Date","Ticker","Open","High","Low","Close","Volume","Currency"]
        for c in cols_full:
            if c not in df.columns: df[c] = np.nan
        df = df[cols_full]
        return df
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
        df = df[["Date","Ticker","Open","High","Low","Close","Volume","Currency"]]
        return df
    except Exception:
        return None

def cross_check(primary_df, secondary_df, tol=0.6):
    try:
        if primary_df is None or secondary_df is None or primary_df.empty or secondary_df.empty:
            return True, ""
        a = primary_df.copy(); a["Date"] = pd.to_datetime(a["Date"]); a = a.dropna(subset=["Date"])
        b = secondary_df.copy(); b["Date"] = pd.to_datetime(b["Date"]); b = b.dropna(subset=["Date"])
        if a.empty or b.empty: return True, ""
        d = min(a["Date"].max(), b["Date"].max())
        a_last = float(a[a["Date"]==d]["Close"].iloc[-1]) if (a["Date"]==d).any() else None
        b_last = float(b[b["Date"]==d]["Close"].iloc[-1]) if (b["Date"]==d).any() else None
        if a_last is None or b_last is None: return True, ""
        diff_pct = abs(a_last - b_last) / max(1e-9, b_last) * 100.0
        return (diff_pct <= tol), f"diff_pct={diff_pct:.2f}% on {d.date()}"
    except Exception as e:
        return True, f"check_error={e}"

def save_csv(df, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

def build_index_and_latest(data_root, latest_dir):
    files = sorted(Path(data_root).glob("*.csv"))
    items = []; latest_rows = []
    for p in files:
        try:
            df = pd.read_csv(p, parse_dates=["Date"])
            if df.empty: continue
            df = df.sort_values("Date")
            last = df.iloc[-1]
            latest_rows.append({
                "Date": last["Date"],
                "Ticker": last.get("Ticker", p.stem),
                "Open": last.get("Open", None),
                "High": last.get("High", None),
                "Low": last.get("Low", None),
                "Close": last.get("Close", None),
                "Volume": last.get("Volume", None),
                "Currency": last.get("Currency", None),
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
    idx = {"count": len(items), "generated_utc": pd.Timestamp.utcnow().isoformat(), "items": items}
    Path(latest_dir, "index.json").write_text(json.dumps(idx, ensure_ascii=False, separators=(",",":")), encoding="utf-8")
    if latest_rows:
        cols = ["Date","Ticker","Open","High","Low","Close","Volume","Currency"]
        pd.DataFrame(latest_rows, columns=cols).to_csv(Path(latest_dir, "eod-latest.csv"), index=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", required=False, default="")
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--latest-dir", required=True)
    ap.add_argument("--min", type=int, default=220)
    ap.add_argument("--tolerance", type=float, default=0.6)
    args = ap.parse_args()

    Path(args.data_root).mkdir(parents=True, exist_ok=True)
    Path(args.latest_dir).mkdir(parents=True, exist_ok=True)

    want = set()
    want |= load_universe(args.universe)
    want |= SEED_ETFS

    # Expand: add venues if missing
    expanded = set()
    for s in want:
        if "." in s: expanded.add(s)
        else:
            for suf in [".MI",".AS",".PA",".DE"]:
                expanded.add(s + suf)

    existing = {p.stem for p in Path(args.data_root).glob("*.csv")}
    to_fetch = sorted(expanded - existing)

    added = 0
    for sym in to_fetch:
        yf_df = fetch_yf(sym)
        stq_df = fetch_stooq(sym)

        ok, note = cross_check(yf_df, stq_df, tol=args.tolerance)
        out = None
        if yf_df is not None and ok:
            out = yf_df
        elif stq_df is not None:
            out = stq_df
        if out is not None:
            save_csv(out, Path(args.data_root, f"{sym}.csv"))
            added += 1

        if (len(existing) + added) >= args.min:
            break

    build_index_and_latest(args.data_root, args.latest_dir)

if __name__ == "__main__":
    main()
