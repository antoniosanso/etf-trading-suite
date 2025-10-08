import argparse
import pandas as pd
from pathlib import Path
import sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--min_rows', type=int, default=1000)
    ap.add_argument('--max_dd_allowed_pct', type=float, default=90.0)
    args = ap.parse_args()

    p = Path(args.data)
    df = pd.read_csv(p)
    # Normalize Date to tz-naive
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], utc=True).dt.tz_localize(None)

    issues = []

    rows = len(df)
    tickers = df['Ticker'].nunique() if 'Ticker' in df.columns else 0
    if rows < args.min_rows:
        issues.append(f"rows_below_min:{rows} < {args.min_rows}")
    if tickers < 1:
        issues.append("no_tickers_detected")

    for col in ['Date','Ticker','Close']:
        if col not in df.columns:
            issues.append(f"missing_col:{col}")
    if 'Close' in df.columns:
        null_close = df['Close'].isna().mean()*100.0
        if null_close > 1.0:
            issues.append(f"close_nan_pct:{null_close:.2f}%")

    if all(c in df.columns for c in ['Ticker','Date']):
        dup = df.duplicated(['Ticker','Date']).sum()
        if dup > 0:
            issues.append(f"duplicate_rows:{dup}")

    print(f"rows={rows} tickers={tickers} date_range={df['Date'].min()}→{df['Date'].max()}")
    if issues:
        print("SANITY: FAIL ->", ", ".join(issues))
        sys.exit(2)
    else:
        print("SANITY: PASS")

if __name__ == "__main__":
    main()
