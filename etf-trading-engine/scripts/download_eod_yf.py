#!/usr/bin/env python3
import argparse, pandas as pd, datetime as dt, sys, time
from pathlib import Path

def fetch_history(sym, start, end):
    import yfinance as yf
    try:
        t = yf.Ticker(sym)
        df = t.history(start=start, end=end, interval="1d", auto_adjust=False)
        if df is None or df.empty:
            df = t.history(period="max", interval="1d", auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index().rename(columns={
            'Date':'Date','Open':'Open','High':'High','Low':'Low','Close':'Close','Volume':'Volume'
        })
        for c in ['Open','High','Low','Close','Volume']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        df['Date'] = pd.to_datetime(df['Date'], utc=True, errors='coerce').dt.tz_localize(None)
        return df[['Date','Open','High','Low','Close','Volume']]
    except Exception as e:
        print(f"[WARN] {sym}: {e}", file=sys.stderr)
        return pd.DataFrame()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--universe', required=True, help='CSV con colonne Ticker e opzionale YF')
    ap.add_argument('--output', required=True, help='File CSV di output')
    ap.add_argument('--start', default="2018-01-01")
    ap.add_argument('--end', default=None)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--sleep', type=float, default=0.15)
    ap.add_argument('--min_success', type=int, default=5)
    args = ap.parse_args()

    uni = pd.read_csv(args.universe)
    if 'YF' in uni.columns:
        uni['Symbol'] = uni['YF'].fillna(uni['Ticker']).astype(str)
    else:
        uni['Symbol'] = uni['Ticker'].astype(str)
    symbols = [s.strip() for s in uni['Symbol'].dropna().unique().tolist() if s and s.strip()!='']
    start = args.start
    end = args.end or dt.date.today().isoformat()

    from concurrent.futures import ThreadPoolExecutor, as_completed
    rows, success, fail = [], 0, 0
    with ThreadPoolExecutor(max_workers=max(args.threads,1)) as ex:
        fut = {ex.submit(fetch_history, s, start, end): s for s in symbols}
        for f in as_completed(fut):
            s = fut[f]
            try:
                df = f.result()
                if not df.empty:
                    df['Ticker'] = s
                    rows.append(df[['Date','Ticker','Open','High','Low','Close','Volume']])
                    success += 1
                else:
                    fail += 1
            except Exception as e:
                print(f"[WARN] {s}: {e}", file=sys.stderr)
                fail += 1
            time.sleep(args.sleep)

    if success < args.min_success:
        print(f"[ERROR] Scaricati {success} ticker (<{args.min_success}). Controlla universe.csv o mapping YF.", file=sys.stderr)
        sys.exit(2)

    out = pd.concat(rows, ignore_index=True).sort_values(['Ticker','Date'])
    Path(Path(args.output).parent).mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"[OK] Salvato {args.output} righe={len(out)} successi={success} fail={fail}")

if __name__ == "__main__":
    main()
