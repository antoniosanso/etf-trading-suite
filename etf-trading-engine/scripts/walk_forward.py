import argparse, yaml, pandas as pd, json, numpy as np
from copy import deepcopy
from pathlib import Path
import sys, os, math

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path: sys.path.insert(0, repo_root)
from src.engine.backtest import run_backtest

def slice_by_dates(df, start, end):
    m = (df['Date']>=pd.Timestamp(start)) & (df['Date']<=pd.Timestamp(end))
    return df.loc[m].copy()

def safe_calmar(k):
    # Ensure Calmar is finite numeric; if not, coerce to 0.0
    c = k.get('Calmar', None)
    try:
        c = float(c)
        if math.isfinite(c):
            return c
        return 0.0
    except Exception:
        return 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--data', required=True)
    ap.add_argument('--windows', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--all-strategies', action='store_true',
                    help='Compare every executable strategy out of sample')
    args = ap.parse_args()

    with open(args.config, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    if args.all_strategies:
        cfg['active_run'] = 'all'

    prices = pd.read_csv(args.data)
    prices['Date'] = pd.to_datetime(prices['Date'], utc=True).dt.tz_localize(None)

    with open(args.windows, 'r', encoding='utf-8') as f:
        wins = yaml.safe_load(f)

    results = []
    for w in wins['windows']:
        name = w['name']
        ts, te = w['test_start'], w['test_end']
        # Include prior history only as indicator warm-up. KPIs and trades are
        # evaluated strictly inside the declared out-of-sample test window.
        train_start = w.get('train_start', str((pd.Timestamp(ts) - pd.DateOffset(years=3)).date()))
        train_end = w.get('train_end', str((pd.Timestamp(ts) - pd.Timedelta(days=1)).date()))
        df = slice_by_dates(prices, train_start, te)
        if len(df) == 0:
            print(f"WF window {name} -> EMPTY ({ts}→{te})")
            continue
        run_cfg = deepcopy(cfg)
        run_cfg.setdefault('general', {})['evaluation'] = {'start': ts, 'end': te}
        out = run_backtest(df, run_cfg)
        window_runs = out.get('runs', {run_cfg.get('active_run', 'active'): out})
        for strategy, run in window_runs.items():
            k = dict(run['kpis'])
            k['Calmar'] = safe_calmar(k)
            k['strategy'] = strategy
            k['window'] = name
            k['test_start'] = ts
            k['test_end'] = te
            k['train_start'] = train_start
            k['train_end'] = train_end
            results.append(k)
            print(f"WF {name}/{strategy}: Sharpe={k.get('Sharpe',float('nan')):.3f} Calmar={k.get('Calmar',0.0):.3f} MaxDD={k.get('MaxDD',float('nan')):.3f} PF={k.get('ProfitFactor',float('nan')):.3f}")

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    if not results:
        (outdir/'wf_summary.txt').write_text("No WF results (empty windows or data).\n", encoding='utf-8')
        (outdir/'wf_report.json').write_text(json.dumps({"windows":[],"aggregates":{}}, indent=2), encoding='utf-8')
        print("WF: no results")
        return

    dfres = pd.DataFrame(results)
    aggregates = {}
    for strategy, group in dfres.groupby('strategy'):
        calmar = pd.to_numeric(group['Calmar'], errors='coerce').values.astype(float)
        mean_c = float(np.nanmean(calmar))
        std_c = float(np.nanstd(calmar))
        aggregates[strategy] = {
            "windows_count": int(len(group)),
            "calmar_mean": mean_c,
            "calmar_std": std_c,
            "calmar_cov_pct": float((std_c / (abs(mean_c)+1e-12))*100.0),
            "sharpe_mean": float(np.nanmean(pd.to_numeric(group['Sharpe'], errors='coerce'))),
            "maxdd_mean": float(np.nanmean(pd.to_numeric(group['MaxDD'], errors='coerce'))),
            "profit_factor_mean": float(np.nanmean(pd.to_numeric(group['ProfitFactor'], errors='coerce'))),
            "trades_total": int(pd.to_numeric(group['Trades'], errors='coerce').fillna(0).sum()),
        }

    (outdir/'wf_report.json').write_text(json.dumps({"windows": results, "aggregates": aggregates}, indent=2), encoding='utf-8')

    with open(outdir/'wf_summary.txt','w',encoding='utf-8') as f:
        f.write("Walk-Forward Summary\n")
        for _, r in dfres.iterrows():
            f.write(f"- {r['window']}/{r['strategy']}: Calmar={float(r['Calmar']):.3f}, Sharpe={float(r['Sharpe']):.3f}, MaxDD={float(r['MaxDD']):.3f}, PF={float(r['ProfitFactor']):.3f}\n")
        for strategy, values in aggregates.items():
            f.write(f"\n{strategy}: calmar_mean={values['calmar_mean']:.3f}, calmar_cov_pct={values['calmar_cov_pct']:.2f}%, trades={values['trades_total']}\n")

    print(f"WF aggregates generated for {len(aggregates)} strategies")

if __name__ == "__main__":
    main()
