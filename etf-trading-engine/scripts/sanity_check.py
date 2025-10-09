#!/usr/bin/env python3
import argparse, pandas as pd, sys
from pathlib import Path

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
    df = pd.read_csv(p)
    required = {'Date','Ticker','Open','High','Low','Close','Volume'}
    if not required.issubset(set(df.columns)):
        print(f"[ERROR] Colonne mancanti. Trovate: {list(df.columns)}", file=sys.stderr)
        sys.exit(2)
    if len(df) < args.min_rows:
        print(f"[ERROR] Poche righe: {len(df)} < {args.min_rows}", file=sys.stderr)
        sys.exit(2)
    # sanity semplice: no Close<=0, no Volume<0
    bad_close = (df['Close']<=0).sum()
    bad_vol = (df['Volume']<0).sum()
    if bad_close>0:
        print(f"[WARN] {bad_close} valori Close<=0", file=sys.stderr)
    if bad_vol>0:
        print(f"[WARN] {bad_vol} valori Volume<0", file=sys.stderr)
    print("[OK] Sanity EOD: PASS")
    sys.exit(0)

if __name__ == '__main__':
    main()
