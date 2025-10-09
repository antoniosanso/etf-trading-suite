import argparse, yaml
from pathlib import Path
import pandas as pd, numpy as np
def atr(df, n=14):
    h, l, c = df['High'], df['Low'], df['Close']
    prev_c = c.shift(1)
    tr = pd.concat([h-l, (h-prev_c).abs(), (l-prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()
def donchian_high(df, n=55):
    return df['High'].rolling(n, min_periods=n).max()
def load_features(feat_cfg_path, features_dir):
    fcfg = yaml.safe_load(open(feat_cfg_path,'r',encoding='utf-8'))
    features_dir = Path(features_dir)
    def try_load(name, cols):
        try:
            t = pd.read_csv(features_dir/name)
            if not t.empty:
                t['Date'] = pd.to_datetime(t['Date'], utc=True).dt.tz_localize(None)
                return t[cols].copy()
        except Exception:
            pass
        return pd.DataFrame(columns=cols)
    sent = try_load('sentiment.csv', ['Date','Ticker','sentiment_z'])
    reg  = try_load('regime.csv',    ['Date','risk_on'])
    fund = try_load('fundamentals.csv', ['Date','Ticker','fundamentals_z'])
    return {
        "sent": sent, "reg": reg, "fund": fund,
        "w_sent": float((fcfg.get('sentiment',{}) or {}).get('weight', 0.0)) if (fcfg.get('sentiment',{}) or {}).get('enabled',False) else 0.0,
        "w_reg":  float((fcfg.get('regime',{}) or {}).get('weight', 0.0)) if (fcfg.get('regime',{}) or {}).get('enabled',False) else 0.0,
        "w_fund": float((fcfg.get('fundamentals',{}) or {}).get('weight', 0.0)) if (fcfg.get('fundamentals',{}) or {}).get('enabled',False) else 0.0,
    }
def run(cfg_path, data_path, outdir, feat_cfg_path='etf-trading-config/features.yaml', features_dir='./features'):
    cfg = yaml.safe_load(open(cfg_path,'r',encoding='utf-8'))
    outdir = Path(outdir); (outdir/'signals').mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(data_path); df['Date'] = pd.to_datetime(df['Date'], utc=True).dt.tz_localize(None)
    df = df.sort_values(['Ticker','Date']); F = load_features(feat_cfg_path, features_dir)
    today = df['Date'].max()
    sent_today = F['sent'][F['sent']['Date']==today].set_index('Ticker')['sentiment_z'] if not F['sent'].empty else pd.Series(dtype=float)
    reg_today  = F['reg'][F['reg']['Date']==today]['risk_on'].mean() if not F['reg'].empty else np.nan
    reg_today  = float(reg_today) if pd.notna(reg_today) else 0.0
    fund_today = F['fund'][F['fund']['Date']==today].set_index('Ticker')['fundamentals_z'] if not F['fund'].empty else pd.Series(dtype=float)
    df['DollarVolume'] = (df['Close'].abs()*df['Volume'].abs())
    res_watch, res_entries = [], []
    for t, g in df.groupby('Ticker', sort=False):
        g = g.copy()
        g['SMA_F'] = g['Close'].rolling(cfg['sma_fast'], min_periods=cfg['sma_fast']).mean()
        g['SMA_S'] = g['Close'].rolling(cfg['sma_slow'], min_periods=cfg['sma_slow']).mean()
        g['ATR'] = atr(g, cfg['atr_period'])
        g['DonchianHigh'] = donchian_high(g, cfg['breakout_lookback'])
        g['mom63'] = g['Close'].pct_change(63); g['mom252'] = g['Close'].pct_change(252)
        g['ADV20'] = g['DollarVolume'].rolling(20, min_periods=1).mean()
        last = g.iloc[-1]; prev = g.iloc[-2] if len(g)>=2 else last
        trend_ok = (last['Close'] > last['SMA_S']) and (last['mom252'] > 0) if cfg.get('trend_filter',True) else True
        breakout_ok = last['Close'] >= prev['DonchianHigh'] if pd.notna(prev['DonchianHigh']) and pd.notna(last['Close']) else False
        cross_ok = (last['Close'] > last['SMA_F']) and (prev['Close'] <= prev['SMA_F']) if pd.notna(prev['SMA_F']) and pd.notna(prev['Close']) and pd.notna(last['SMA_F']) else False
        liquid_ok = (last['ADV20'] >= cfg['min_adv20']) or (last['Volume'] >= cfg['min_volume'])
        vol_ok = pd.notna(last['ATR']) and (last['ATR'] > 0)
        sent_z = float(sent_today.get(t, 0.0)) if len(sent_today)>0 else 0.0
        fund_z = float(fund_today.get(t, 0.0)) if len(fund_today)>0 else 0.0
        rank_score = (cfg['rank_weights']['mom252'] * (last['mom252'] if pd.notna(last['mom252']) else 0.0) +
                      cfg['rank_weights']['mom63']  * (last['mom63']  if pd.notna(last['mom63'])  else 0.0) +
                      F['w_sent'] * sent_z + F['w_reg'] * reg_today + F['w_fund'] * fund_z)
        watch = {'Date': last['Date'].date(), 'Ticker': t, 'Close': float(last['Close']),
                 'RankScore': float(rank_score), 'SentimentZ': sent_z, 'RegimeZ': reg_today, 'FundamentalsZ': fund_z}
        res_watch.append(watch)
        if trend_ok and (breakout_ok or cross_ok) and liquid_ok and vol_ok:
            entry = float(last['Close']); risk = float(cfg['atr_mult_sl']) * float(g['ATR'].iloc[-1])
            if not np.isfinite(risk) or risk<=0: continue
            stop = entry - risk; R = entry - stop
            tp_levels = [entry + r*R for r in cfg.get('tp_r_multiples', [2.0,3.0])]
            equity = float(cfg.get('equity_base', 100000)); risk_dollar = equity * float(cfg.get('risk_per_trade_pct',0.01))
            size = int(np.floor(risk_dollar / R)) if R>0 else 0
            res_entries.append({'Date': watch['Date'], 'Ticker': t, 'Entry': entry, 'StopLoss': stop,
                                'TP1': tp_levels[0] if len(tp_levels)>0 else None,
                                'TP2': tp_levels[1] if len(tp_levels)>1 else None,
                                'SizeShares': size, 'R': R, 'SentimentZ': sent_z, 'RegimeZ': reg_today,
                                'FundamentalsZ': fund_z, 'RankScore': float(rank_score)})
    pd.DataFrame(res_watch).sort_values('RankScore', ascending=False).to_csv(outdir/'signals'/'watchlist_today.csv', index=False)
    pd.DataFrame(res_entries).sort_values('RankScore', ascending=False).head(int(cfg['top_n'])).to_csv(outdir/'signals'/'entries_today.csv', index=False)
    print("signals: entries_today.csv & watchlist_today.csv (sentiment/regime/fundamentals)")
if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True); ap.add_argument('--data', required=True); ap.add_argument('--outdir', required=True)
    ap.add_argument('--features_cfg', default='etf-trading-config/features.yaml'); ap.add_argument('--features_dir', default='./features')
    a = ap.parse_args(); run(a.config, a.data, a.outdir, a.features_cfg, a.features_dir)
