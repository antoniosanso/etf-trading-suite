import argparse, pandas as pd, numpy as np
from pathlib import Path
def fetch_top_holdings(etf, max_n=15):
    try:
        import yfinance as yf
        t = yf.Ticker(etf); holds = []
        for attr in ['fund_holdings','holdings']:
            if hasattr(t, attr):
                data = getattr(t, attr)
                if isinstance(data, dict) and 'holdings' in data:
                    for row in data['holdings'][:max_n]:
                        holds.append((row.get('symbol') or row.get('ticker') or '', float(row.get('holdingPercent',0.0))))
                elif isinstance(data, list):
                    for row in data[:max_n]:
                        sym = row.get('symbol') or row.get('ticker') or ''
                        wgt = float(row.get('holdingPercent',0.0) or row.get('weight',0.0))
                        holds.append((sym, wgt))
        out = []
        for s,w in holds:
            s = (s or '').upper().strip()
            if s and w>0: out.append((s,w))
        return out[:max_n]
    except Exception: return []
def fetch_fundamentals(tickers):
    try: import yfinance as yf
    except Exception: return {}
    vals = {}
    for s in tickers:
        try:
            tk = yf.Ticker(s)
            info = {}; 
            try: info = tk.info or {}
            except: info = {}
            rev = float(info.get('revenueGrowth', 0.0) or 0.0)
            margin = float(info.get('operatingMargins', 0.0) or 0.0)
            vals[s] = (rev, margin)
        except Exception: continue
    if not vals: return {}
    import pandas as pd, numpy as np
    R = pd.Series({k:v[0] for k,v in vals.items()}); M = pd.Series({k:v[1] for k,v in vals.items()})
    Rz = (R-R.mean())/(R.std(ddof=0)+1e-12); Mz = (M-M.mean())/(M.std(ddof=0)+1e-12)
    return {k: float(np.nanmean([Rz.get(k,0.0), Mz.get(k,0.0)])) for k in vals.keys()}
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--universe', required=True); ap.add_argument('--outdir', required=True)
    ap.add_argument('--max_holdings', type=int, default=15); a = ap.parse_args()
    uni = pd.read_csv(a.universe); uni['Ticker']=uni['Ticker'].astype(str)
    today = pd.Timestamp.utcnow().tz_localize(None).normalize(); rows = []
    for etf in uni['Ticker'].unique().tolist():
        holds = fetch_top_holdings(etf, a.max_holdings); 
        if not holds: continue
        tickers = [h[0] for h in holds if h[0]]; weights = np.array([h[1] for h in holds if h[0]], dtype=float)
        if weights.sum()==0: continue
        weights = weights/weights.sum(); f = fetch_fundamentals(tickers)
        if not f: continue
        vect = np.array([f.get(t,0.0) for t in tickers], dtype=float); score = float(np.dot(weights, vect))
        rows.append({'Date':today, 'Ticker':etf, 'fundamentals_raw':score})
    feat = pd.DataFrame(rows)
    if not feat.empty:
        grp = feat.groupby('Date')['fundamentals_raw']
        feat['fundamentals_z'] = grp.transform(lambda s: (s-s.mean())/(s.std(ddof=0)+1e-12))
    else:
        feat = pd.DataFrame(columns=['Date','Ticker','fundamentals_raw','fundamentals_z'])
    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    feat.to_csv(Path(a.outdir)/'fundamentals.csv', index=False); print(f'fundamentals: wrote {len(feat)} rows')
if __name__=='__main__': main()
