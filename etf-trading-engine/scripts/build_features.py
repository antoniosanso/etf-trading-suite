import argparse, yaml, pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
def zscore(s, win=None):
    if win:
        return (s - s.rolling(win, min_periods=1).mean())/(s.rolling(win, min_periods=1).std(ddof=0)+1e-12)
    return (s - s.mean())/(s.std(ddof=0)+1e-12)
def build_regime(vix_symbol="^VIX", credit_pair=("HYG","IEF"), smoothing_days=5):
    import yfinance as yf
    end = datetime.now(timezone.utc); start = end - timedelta(days=800)
    vix = yf.download(vix_symbol, start=start.date().isoformat(), end=end.date().isoformat(), interval="1d", progress=False)
    vix = vix[['Adj Close']].rename(columns={'Adj Close':'VIX'}).reset_index()
    vix['Date'] = pd.to_datetime(vix['Date'], utc=True).dt.tz_localize(None)
    a = yf.download(credit_pair[0], start=start.date().isoformat(), end=end.date().isoformat(), interval="1d", progress=False)[['Adj Close']].rename(columns={'Adj Close':credit_pair[0]})
    b = yf.download(credit_pair[1], start=start.date().isoformat(), end=end.date().isoformat(), interval="1d", progress=False)[['Adj Close']].rename(columns={'Adj Close':credit_pair[1]})
    cr = a.join(b, how='inner'); cr['CRATIO'] = cr[credit_pair[0]]/(cr[credit_pair[1]]+1e-12)
    cr = cr.reset_index().rename(columns={'index':'Date'}); cr['Date'] = pd.to_datetime(cr['Date'], utc=True).dt.tz_localize(None)
    vix['VIX_z'] = zscore(vix['VIX'], win=126); cr['CRATIO_z'] = zscore(cr['CRATIO'], win=126)
    reg = pd.merge_asof(vix.sort_values('Date'), cr.sort_values('Date'), on='Date')
    reg['risk_on_raw'] = (-reg['VIX_z'].fillna(0) + cr['CRATIO_z'].fillna(0))/2.0
    reg['risk_on'] = zscore(reg['risk_on_raw'].rolling(smoothing_days, min_periods=1).mean())
    return reg[['Date','risk_on']].dropna()
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--features', required=True)
    ap.add_argument('--universe', required=True); ap.add_argument('--outdir', required=True)
    a = ap.parse_args(); cfg = yaml.safe_load(open(a.features,'r',encoding='utf-8'))
    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)
    src = (cfg.get('sentiment',{}) or {}).get('source','').lower()
    if src != 'multi': print("features: source!=multi (nessuna azione sul sentiment in questa patch)")
    reg = pd.DataFrame(columns=['Date','risk_on'])
    if cfg.get('regime',{}).get('enabled',False):
        pair = cfg['regime'].get('credit_risk_ratio',['HYG','IEF'])
        reg = build_regime(cfg['regime'].get('vix_symbol','^VIX'), tuple(pair), cfg['regime'].get('smoothing_days',5))
    reg.to_csv(outdir/'regime.csv', index=False); print(f"features: wrote regime.csv ({len(reg)})")
if __name__ == '__main__': main()
