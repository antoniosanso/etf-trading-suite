#!/usr/bin/env python3
import argparse, pandas as pd, sys
from pathlib import Path

def to_num(s):
    return pd.to_numeric(s, errors='coerce')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='CSV con colonne Date,Ticker,Open,High,Low,Close,Volume')
    ap.add_argument('--min_rows', type=int, default=1000)
    ap.add_argument('--max_dd_allowed_pct', type=float, default=90.0)
    args = ap.parse_args()

    p = Path(args.data)
    if not p.exists():
        print(f"[ERROR] File non trovato: {p}", file=sys.stderr)
        sys.exit(2)
    # low_memory=False per evitare dtypes misti
    df = pd.read_csv(p, low_memory=False)

    required = ['Date','Ticker','Open','High','Low','Close','Volume']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"[ERROR] Colonne mancanti: {missing} – trovate: {list(df.columns)}", file=sys.stderr)
        sys.exit(2)

    # Coerci numerici
    for c in ['Open','High','Low','Close','AdjClose','Volume']:
        if c in df.columns:
            df[c] = to_num(df[c])

    if len(df) < args.min_rows:
        print(f"[ERROR] Poche righe: {len(df)} < {args.min_rows}", file=sys.stderr)
        sys.exit(2)

    bad_close = int((df['Close'].fillna(-1) <= 0).sum())
    bad_vol = int((df['Volume'].fillna(-1) < 0).sum()) if 'Volume' in df.columns else 0
    if bad_close > 0:
        print(f"[WARN] {bad_close} valori Close<=0 (o NaN)", file=sys.stderr)
    if bad_vol > 0:
        print(f"[WARN] {bad_vol} valori Volume<0 (o NaN)", file=sys.stderr)

    # Check duplicati/Date non parse
    try:
        df['Date'] = pd.to_datetime(df['Date'], utc=True, errors='coerce').dt.tz_localize(None)
    except Exception:
        pass
    nan_dates = int(df['Date'].isna().sum())
    if nan_dates > 0:
        print(f"[WARN] {nan_dates} Date non parse (NaN)", file=sys.stderr)

    print("[OK] Sanity EOD: PASS")
    sys.exit(0)

if __name__ == '__main__':
    main()
