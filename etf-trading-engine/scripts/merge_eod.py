import argparse
from pathlib import Path
import pandas as pd
import re

EXCLUDE_PATTERNS = ['portfolio','report','equity','compare','bh_','benchmark']

COLMAP = {
    'Date':   ['Date','DATA','Data','date','dt','Timestamp','Datetime','DateTime','time'],
    'Ticker': ['Ticker','Symbol','SYMBOL','Asset','Name','Instrument','Code','ticker'],
    'Open':   ['Open','Apertura','open','OPEN'],
    'High':   ['High','Massimo','Max','high','HIGH'],
    'Low':    ['Low','Minimo','Min','low','LOW'],
    'Close':  ['Close','Chiusura','close','Adj Close','adj_close','AdjClose','Last','Price','Closing Price','Ultimo','PREZZO','Prezzo'],
    'Volume': ['Volume','Vol','VOL','volume','Qty','Q.ta','Turnover']
}

def pick_col(cols, aliases):
    s = set(c.strip() for c in cols)
    for a in aliases:
        if a in s:
            return a
    low = {c.lower(): c for c in s}
    for a in aliases:
        if a.lower() in low:
            return low[a.lower()]
    return None

def is_excluded(name: str) -> bool:
    name = name.lower()
    return any(pat in name for pat in EXCLUDE_PATTERNS)

def infer_ticker_from_name(name: str) -> str:
    stem = Path(name).stem
    stem = re.split(r'[_\-]', stem)[0]
    return stem.upper()

def smart_read_csv(path: Path):
    for kwargs in [
        {'sep': None, 'engine': 'python', 'encoding': 'utf-8-sig'},
        {'sep': ';',  'engine': 'python', 'encoding': 'utf-8-sig', 'decimal': ','},
        {'sep': ',',  'engine': 'python', 'encoding': 'utf-8-sig', 'decimal': '.'},
        {'sep': ';',  'engine': 'python', 'encoding': 'latin1', 'decimal': ','},
        {'sep': ',',  'engine': 'python', 'encoding': 'latin1', 'decimal': '.'},
    ]:
        try:
            df = pd.read_csv(path, **kwargs)
            if df.shape[1] == 1:
                continue
            return df
        except Exception:
            continue
    raise ValueError("Unable to parse CSV with common delimiters/encodings")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--datalake', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--recursive', action='store_true')

    ap.add_argument('--datecol')
    ap.add_argument('--tickercol')
    ap.add_argument('--closecol')
    ap.add_argument('--opencol')
    ap.add_argument('--highcol')
    ap.add_argument('--lowcol')
    ap.add_argument('--volumecol')

    args = ap.parse_args()

    datalake_path = Path(args.datalake)
    output_path = Path(args.output)
    files = list(datalake_path.rglob("*.csv")) if args.recursive else list(datalake_path.glob("*.csv"))

    good_frames = []
    skipped = 0
    for f in files:
        if is_excluded(f.name):
            skipped += 1
            print(f"⚠️  File escluso (pattern): {f.name}")
            continue
        try:
            df = smart_read_csv(f)
        except Exception as e:
            print(f"⚠️  Impossibile leggere {f.name}: {e}")
            continue

        cols = list(df.columns)
        col_Date   = args.datecol   if args.datecol   else pick_col(cols, COLMAP['Date'])
        col_Close  = args.closecol  if args.closecol  else pick_col(cols, COLMAP['Close'])
        col_Open   = args.opencol   if args.opencol   else pick_col(cols, COLMAP['Open'])
        col_High   = args.highcol   if args.highcol   else pick_col(cols, COLMAP['High'])
        col_Low    = args.lowcol    if args.lowcol    else pick_col(cols, COLMAP['Low'])
        col_Volume = args.volumecol if args.volumecol else pick_col(cols, COLMAP['Volume'])
        col_Ticker = args.tickercol if args.tickercol else pick_col(cols, COLMAP['Ticker'])

        if not col_Date or not col_Close:
            print(f"⚠️  File ignorato (mancano colonne essenziali Date/Close): {f.name} | Colonne trovate: {cols}")
            continue

        out = pd.DataFrame()
        out['Date'] = pd.to_datetime(df[col_Date], errors='coerce')
        def numify(s): return pd.to_numeric(s.astype(str).str.replace(',','.'), errors='coerce')
        out['Close']  = numify(df[col_Close])
        out['Open']   = numify(df[col_Open]) if col_Open is not None else out['Close']
        out['High']   = numify(df[col_High]) if col_High is not None else out['Close']
        out['Low']    = numify(df[col_Low])  if col_Low  is not None else out['Close']
        out['Volume'] = numify(df[col_Volume]) if col_Volume is not None else 0

        if col_Ticker:
            out['Ticker'] = df[col_Ticker].astype(str).str.upper().str.strip()
        else:
            out['Ticker'] = infer_ticker_from_name(f.name)

        out['Currency'] = 'EUR'
        out = out.dropna(subset=['Date','Close'])
        if out.empty:
            print(f"⚠️  Nessun dato valido in: {f.name}")
            continue

        good_frames.append(out)

    if not good_frames:
        raise SystemExit("❌ Nessun file valido trovato.")

    merged = pd.concat(good_frames, ignore_index=True)
    merged = merged.sort_values(['Ticker','Date']).drop_duplicates(['Ticker','Date'], keep='last')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    print(f"✅ Salvato {output_path.resolve()} — righe: {len(merged):,}, ETF: {merged['Ticker'].nunique()} (skippati: {skipped})")

if __name__ == '__main__':
    main()
