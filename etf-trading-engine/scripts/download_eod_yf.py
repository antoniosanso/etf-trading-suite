#!/usr/bin/env python3
import argparse, pandas as pd, datetime as dt, sys, time
from pathlib import Path

def fetch_ticker(ticker, start, end):
    import yfinance as yf
    try:
        df = yf.download(ticker, start=start, end=end, interval="1d", progress=False, auto_adjust=False)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index().rename(columns={
            'Date':'Date',
            'Open':'Open','High':'High','Low':'Low','Close':'Close','Adj Close':'AdjClose','Volume':'Volume'
        })
        df['Ticker'] = str(ticker)
        df['Date'] = pd.to_datetime(df['Date'], utc=True).dt.tz_localize(None)
        for c in ['Open','High','Low','Close','AdjClose','Volume']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        return df[['Date','Ticker','Open','High','Low','Close','AdjClose','Volume']]
    except Exception as e:
        print(f"[WARN] {ticker}: {e}", file=sys.stderr)
        return pd.DataFrame()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--universe', required=True, help='CSV con colonna Ticker')
    ap.add_argument('--output', required=True, help='File CSV di output')
    ap.add_argument('--start', default="2018-01-01")
    ap.add_argument('--end', default=None)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--sleep', type=float, default=0.2)
    ap.add_argument('--adjusted', action='store_true')
    args = ap.parse_args()

    uni = pd.read_csv(args.universe)
    tickers = [str(t).strip() for t in uni['Ticker'].dropna().unique().tolist()]
    start = args.start
    end = args.end or dt.date.today().isoformat()

    from concurrent.futures import ThreadPoolExecutor, as_completed
    out = []
    with ThreadPoolExecutor(max_workers=max(args.threads,1)) as ex:
        fut = {ex.submit(fetch_ticker, t, start, end): t for t in tickers}
        for f in as_completed(fut):
            t = fut[f]
            try:
                df = f.result()
                if not df.empty:
                    out.append(df)
            except Exception as e:
                print(f"[WARN] {t}: {e}", file=sys.stderr)
            time.sleep(args.sleep)
    if not out:
        print("[ERROR] Nessun dato scaricato. Controlla universe.csv", file=sys.stderr)
        sys.exit(2)
    big = pd.concat(out, ignore_index=True).sort_values(['Ticker','Date'])
    Path(Path(args.output).parent).mkdir(parents=True, exist_ok=True)
    big.to_csv(args.output, index=False)
    print(f"[OK] Salvato {args.output} righe={len(big)} tickers={len(tickers)}")

if __name__ == "__main__":
    main()
