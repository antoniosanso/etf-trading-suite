import argparse, time, concurrent.futures as cf
from pathlib import Path
import pandas as pd
import yfinance as yf

def fetch_one(ticker, start, adjusted):
    try:
        df = yf.download(ticker, start=start, progress=False, auto_adjust=False, actions=False, interval='1d', threads=False)
        if df is None or df.empty:
            return None
        df = df.reset_index().rename(columns={'Date':'Date','Open':'Open','High':'High','Low':'Low','Close':'Close','Adj Close':'AdjClose','Volume':'Volume'})
        if adjusted and 'AdjClose' in df.columns and df['AdjClose'].notna().any():
            df['Close'] = df['AdjClose']
        df['Ticker'] = ticker.upper()
        df['Currency'] = 'NA'
        return df[['Date','Ticker','Open','High','Low','Close','Volume','Currency']]
    except Exception as e:
        print(f"⚠️  {ticker}: {e}")
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--universe', required=True, help='CSV with a column Ticker')
    ap.add_argument('--output', required=True)
    ap.add_argument('--start', default='2018-01-01')
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--sleep', type=float, default=0.25, help='Delay between requests per worker')
    ap.add_argument('--adjusted', action='store_true', help='Use Adj Close as Close when available')
    args = ap.parse_args()

    uni = pd.read_csv(args.universe)
    tickers = sorted({t.strip() for t in uni['Ticker'].astype(str) if t and t.strip()})
    out_frames = []

    def worker(t):
        df = fetch_one(t, args.start, args.adjusted)
        time.sleep(args.sleep)
        return df

    with cf.ThreadPoolExecutor(max_workers=max(1,args.threads)) as ex:
        for df in ex.map(worker, tickers):
            if df is not None and not df.empty:
                out_frames.append(df)

    if not out_frames:
        raise SystemExit('❌ Nessun dato scaricato da Yahoo. Controlla i ticker.')

    merged = pd.concat(out_frames, ignore_index=True).dropna(subset=['Date','Close'])
    merged = merged.sort_values(['Ticker','Date']).drop_duplicates(['Ticker','Date'], keep='last')
    Path(Path(args.output).parent).mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output, index=False)
    print(f"✅ Salvato {args.output} — righe: {len(merged):,}, ETF: {merged['Ticker'].nunique()}")

if __name__ == '__main__':
    main()
