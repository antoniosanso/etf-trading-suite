
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drop-in signals generator (robust).
- Parses CLI args used in the suite
- Loads config YAML
- Loads EOD data
- Loads/derives features (mom252, mom63, ADV20, Volume) if missing
- Builds RankScore from rank_weights
- Applies liquidity filters (min_adv20, min_volume)
- Writes outputs/signals/entries_today.csv using cfg['top_n'] (default 10)
No KeyError on missing columns: everything degrades gracefully.
"""
import os
import sys
import argparse
import warnings
from typing import Dict, Any

import pandas as pd

try:
    import yaml
except Exception as e:
    print("ERROR: pyyaml is required. pip install pyyaml", file=sys.stderr)
    raise

def _read_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _safe_get(d: Dict[str, Any], key: str, default):
    v = d.get(key, default)
    try:
        if v is None:
            return default
    except Exception:
        pass
    return v

def _ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def _last_by_ticker(s: pd.Series) -> pd.Series:
    return s.groupby(level=0).last()

def _prepare_eod(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Try to standardize column names
    cols = {c.lower(): c for c in df.columns}
    # Expected: Ticker, Date, Close, Volume
    # Set index to (Ticker, Date) for group operations
    ticker_col = cols.get('ticker') or 'Ticker'
    date_col   = cols.get('date')   or 'Date'
    if 'Close' not in df.columns and 'close' in cols:  # map close
        df.rename(columns={cols['close']:'Close'}, inplace=True)
    if 'Volume' not in df.columns and 'volume' in cols:
        df.rename(columns={cols['volume']:'Volume'}, inplace=True)

    # parse date and sort
    if date_col not in df.columns:
        raise ValueError(f"EOD file must include a Date column; found: {df.columns.tolist()}")
    df[date_col] = pd.to_datetime(df[date_col])
    df.sort_values([ticker_col, date_col], inplace=True)
    df.set_index([ticker_col, date_col], inplace=True)
    return df

def _rolling_return(df: pd.DataFrame, window: int) -> pd.Series:
    # percentage return over window
    if 'Close' not in df.columns:
        return pd.Series(dtype=float)
    close = df['Close']
    ret = close / close.groupby(level=0).shift(window) - 1.0
    return ret

def _adv(df: pd.DataFrame, window: int = 20) -> pd.Series:
    if 'Volume' not in df.columns:
        return pd.Series(dtype=float)
    vol = df['Volume']
    adv = vol.groupby(level=0).rolling(window).mean().reset_index(level=0, drop=True)
    return adv

def _load_features_dir(features_dir: str) -> pd.DataFrame:
    # Tries to load CSVs in features_dir and left-join by latest per ticker
    if not features_dir or not os.path.isdir(features_dir):
        return pd.DataFrame()
    frames = []
    for fname in os.listdir(features_dir):
        if not fname.lower().endswith(".csv"):
            continue
        try:
            fpath = os.path.join(features_dir, fname)
            df = pd.read_csv(fpath)
            if 'Ticker' in df.columns and 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.sort_values(['Ticker', 'Date'], inplace=True)
                last = df.groupby('Ticker').tail(1).set_index('Ticker')
                last.drop(columns=[c for c in ['Date'] if c in last.columns], inplace=True, errors='ignore')
                frames.append(last)
            elif 'Ticker' in df.columns:
                frames.append(df.set_index('Ticker'))
        except Exception as e:
            warnings.warn(f"Skipping features file {fname}: {e}")
    if not frames:
        return pd.DataFrame()
    out = frames[0]
    for fr in frames[1:]:
        out = out.join(fr, how='outer', rsuffix="_dup")
    out = out.groupby(out.index).last()
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--data", required=True, help="Path to EOD CSV")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--features_cfg", default=None)
    ap.add_argument("--features_dir", default=None)
    args = ap.parse_args()

    cfg = _read_yaml(args.config)
    outdir = args.outdir
    _ensure_dir(outdir)
    _ensure_dir(os.path.join(outdir, "signals"))

    # Defaults to be safe
    top_n          = int(_safe_get(cfg, "top_n", 10))
    rank_weights   = _safe_get(cfg, "rank_weights", {"mom252": 0.6, "mom63": 0.4})
    min_adv20      = float(_safe_get(cfg, "min_adv20", 0))
    min_volume     = float(_safe_get(cfg, "min_volume", 0))

    # Load EOD
    eod = _prepare_eod(args.data)

    # Load latest features from dir (optional)
    feat_last = _load_features_dir(args.features_dir)

    # Build base feature table (latest per ticker)
    base = pd.DataFrame(index=eod.index.get_level_values(0).unique())
    # Momentum
    base['mom252'] = _last_by_ticker(_rolling_return(eod, 252))
    # allow mom63 or mom6 depending on config/scripts
    base['mom63']  = _last_by_ticker(_rolling_return(eod, 63))
    base['mom6']   = _last_by_ticker(_rolling_return(eod, 126)) * 0.0  # placeholder if script expects key
    # Liquidity
    base['ADV20']  = _last_by_ticker(_adv(eod, 20))
    base['Volume'] = _last_by_ticker(eod['Volume']) if 'Volume' in eod.columns else 0.0

    # Merge with external features if provided (left join)
    if not feat_last.empty:
        base = base.join(feat_last, how='left')

    # Apply liquidity filters
    liquid_ok = ( (base.get('ADV20', pd.Series(0.0, index=base.index)) >= min_adv20) |
                  (base.get('Volume', pd.Series(0.0, index=base.index)) >= min_volume) )
    base = base[liquid_ok]

    # Compute RankScore
    rs = pd.Series(0.0, index=base.index)
    if isinstance(rank_weights, dict) and rank_weights:
        for k, w in rank_weights.items():
            if k in base.columns:
                rs = rs + base[k].fillna(0.0) * float(w)
    base['RankScore'] = rs

    # Build entries list
    res_entries = base.reset_index().rename(columns={'index':'Ticker'}).to_dict(orient='records')

    # Sort & write
    df = pd.DataFrame(res_entries)
    score_candidates = ['RankScore', 'rank_score', 'score']
    score_col = next((c for c in score_candidates if c in df.columns), 'RankScore')
    (df.sort_values(score_col, ascending=False)
       .head(top_n)
       .to_csv(os.path.join(outdir, 'signals', 'entries_today.csv'), index=False))

    print(f"Wrote {min(top_n, len(df))} entries to {os.path.join(outdir, 'signals', 'entries_today.csv')}")

if __name__ == "__main__":
    sys.exit(main())
