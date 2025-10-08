import argparse, time, concurrent.futures as cf
from pathlib import Path
import pandas as pd
import yfinance as yf

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Flatten multiindex if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join([str(x) for x in c if x!='']) for c in df.columns.values]
    # Standard rename map
    ren = {
        'Date':'Date', 'Datetime':'Date',
        'Open':'Open','High':'High','Low':'Low',
        'Close':'Close','Adj Close':'AdjClose','AdjClose':'AdjClose',
        'Volume':'Volume'
    }
    cols = {c: ren.get(c, c) for c in df.columns}
    out = df.rename(columns=cols)
    return out

def fetch_one(ticker: str, start: str, adjusted: bool) -> pd.DataFrame | None:
    try:
        t = yf.Ticker(ticker)
        df = t.history(start=start, interval='1d', auto_adjust=False, actions=False)
        if df is None or getattr(df, 'empty', True):
            return None
        df = df.reset_index()
        df = normalize_columns(df)
        needed = {'Date','Close'}
        if not needed.issubset(set(df.columns)):
            return None
        # If requested, prefer AdjClose when available and numeric
        if adjusted and 'AdjClose' in df.columns:
            adj = pd.to_numeric(df['AdjClose'], errors='coerce')
            close = pd.to_numeric(df['Close'], errors='coerce')
            # Use AdjClose where valid, otherwise fallback to Close
            df['Close'] = adj.where(adj.notna(), close)
        # Add required fields
        df['Ticker'] = str(ticker).upper()
        if 'Open' not in df.columns:   df['Open'] = df['Close']
        if 'High' not in df.columns:   df['High'] = df['Close']
        if 'Low'  not in df.columns:   df['Low']  = df['Close']
        if 'Volume' not in df.columns: df['Volume'] = 0
        df['Currency'] = 'NA'
        # Keep standard order
        out = df[['Date','Ticker','Open','High','Low','Close','Volume','Currency']].copy()
        out['Date'] = pd.to_datetime(out['Date'], errors='coerce')
        out = out.dropna(subset=['Date','Close'])
        return out
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
    ap.add_argument('--adjusted', action='store_true', help='Use Adj Close preference when available')
    args = ap.parse_args()

    uni = pd.read_csv(args.universe)
    tickers = [str(t).strip() for t in uni['Ticker'].astype(str).tolist() if str(t).strip()]
    tickers = sorted(set(tickers))

    out_frames: list[pd.DataFrame] = []

    def worker(t):
        df = fetch_one(t, args.start, args.adjusted)
        time.sleep(max(0.0, args.sleep))
        return df

    with cf.ThreadPoolExecutor(max_workers=max(1, args.threads)) as ex:
        for df in ex.map(worker, tickers):
            if df is not None and not df.empty:
                out_frames.append(df)

    if not out_frames:
        raise SystemExit("❌ Nessun dato scaricato da Yahoo. Controlla i ticker.")

    merged = pd.concat(out_frames, ignore_index=True).dropna(subset=['Date','Close'])
    merged = merged.sort_values(['Ticker','Date']).drop_duplicates(['Ticker','Date'], keep='last')
    Path(Path(args.output).parent).mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output, index=False)
    print(f"✅ Salvato {args.output} — righe: {len(merged):,}, ETF: {merged['Ticker'].nunique()}")

if __name__ == '__main__':
    main()
