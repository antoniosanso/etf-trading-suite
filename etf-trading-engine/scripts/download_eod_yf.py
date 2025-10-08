import argparse, time, concurrent.futures as cf
from pathlib import Path
import pandas as pd
import yfinance as yf

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join([str(x) for x in c if x!='']) for c in df.columns.values]
    ren = {'Date':'Date','Datetime':'Date','Open':'Open','High':'High','Low':'Low','Close':'Close','Adj Close':'AdjClose','AdjClose':'AdjClose','Volume':'Volume'}
    return df.rename(columns={c: ren.get(c, c) for c in df.columns})

def fetch_one(ticker: str, start: str, adjusted: bool):
    try:
        t = yf.Ticker(ticker)
        df = t.history(start=start, interval='1d', auto_adjust=False, actions=False)
        if df is None or getattr(df, 'empty', True):
            return None
        df = df.reset_index()
        df = normalize_columns(df)
        if adjusted and 'AdjClose' in df.columns:
            adj = pd.to_numeric(df['AdjClose'], errors='coerce')
            close = pd.to_numeric(df['Close'], errors='coerce')
            df['Close'] = adj.where(adj.notna(), close)
        df['Ticker'] = str(ticker).upper()
        for c in ['Open','High','Low','Close','Volume']:
            if c not in df.columns:
                df[c] = 0 if c=='Volume' else df.get('Close', 0)
        df['Currency'] = 'NA'
        out = df[['Date','Ticker','Open','High','Low','Close','Volume','Currency']].copy()
        out['Date'] = pd.to_datetime(out['Date'], utc=True).dt.tz_localize(None)
        out = out.dropna(subset=['Date','Close'])
        return out
    except Exception as e:
        print(f"⚠️  {ticker}: {e}")
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--universe', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--start', default='2018-01-01')
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--sleep', type=float, default=0.25)
    ap.add_argument('--adjusted', action='store_true')
    args = ap.parse_args()

    uni = pd.read_csv(args.universe)
    tickers = sorted({str(t).strip() for t in uni['Ticker'].astype(str) if str(t).strip()})
    out_frames = []

    def worker(t):
        df = fetch_one(t, args.start, args.adjusted)
        time.sleep(max(0.0, args.sleep))
        return df

    with cf.ThreadPoolExecutor(max_workers=max(1, args.threads)) as ex:
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
