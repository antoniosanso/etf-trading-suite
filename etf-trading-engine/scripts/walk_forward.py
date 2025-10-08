import argparse, yaml, pandas as pd, json
from pathlib import Path
import numpy as np
import sys, os

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path: sys.path.insert(0, repo_root)
from src.engine.backtest import run_backtest

def slice_by_dates(df, start, end):
    m = (df['Date']>=pd.Timestamp(start)) & (df['Date']<=pd.Timestamp(end))
    return df.loc[m].copy()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--data', required=True)
    ap.add_argument('--windows', required=True)
    ap.add_argument('--outdir', required=True)
    args = ap.parse_args()

    with open(args.config, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    prices = pd.read_csv(args.data)
    # Normalize to tz-naive in UTC
    prices['Date'] = pd.to_datetime(prices['Date'], utc=True).dt.tz_localize(None)

    with open(args.windows, 'r', encoding='utf-8') as f:
        wins = yaml.safe_load(f)

    results = []
    for w in wins['windows']:
        name = w['name']
        ts, te = w['test_start'], w['test_end']
        df = slice_by_dates(prices, ts, te)
        if len(df) == 0:
            print(f"WF window {name} -> EMPTY ({ts}→{te})")
            continue
        out = run_backtest(df, cfg)
        k = out['kpis']
        k['window'] = name
        k['test_start'] = ts
        k['test_end'] = te
        results.append(k)
        print(f"WF {name}: Sharpe={k['Sharpe']:.3f} Calmar={k['Calmar']:.3f} MaxDD={k['MaxDD']:.3f} PF={k['ProfitFactor']:.3f}")

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    if not results:
        with open(outdir/'wf_summary.txt','w',encoding='utf-8') as f:
            f.write("No WF results (empty windows or data).\n")
        with open(outdir/'wf_report.json','w',encoding='utf-8') as f:
            json.dump({"windows":[],"aggregates":{}}, f, indent=2)
        print("WF: no results")
        return

    dfres = pd.DataFrame(results)
    calmar = dfres['Calmar'].values
    mean_c = float(np.nanmean(calmar))
    std_c = float(np.nanstd(calmar))
    cov_pct = float((std_c / (abs(mean_c)+1e-12))*100.0)

    aggregates = {
        "windows_count": int(len(dfres)),
        "calmar_mean": mean_c,
        "calmar_std": std_c,
        "calmar_cov_pct": cov_pct,
        "sharpe_mean": float(np.nanmean(dfres['Sharpe'])),
        "maxdd_mean": float(np.nanmean(dfres['MaxDD'])),
        "profit_factor_mean": float(np.nanmean(dfres['ProfitFactor'])),
    }

    with open(outdir/'wf_report.json','w',encoding='utf-8') as f:
        json.dump({"windows": results, "aggregates": aggregates}, f, indent=2)

    with open(outdir/'wf_summary.txt','w',encoding='utf-8') as f:
        f.write("Walk-Forward Summary\n")
        for _, r in dfres.iterrows():
            f.write(f"- {r['window']}: Calmar={r['Calmar']:.3f}, Sharpe={r['Sharpe']:.3f}, MaxDD={r['MaxDD']:.3f}, PF={r['ProfitFactor']:.3f}\n")
        f.write(f"\nAggregates: calmar_mean={mean_c:.3f}, calmar_cov_pct={cov_pct:.2f}%\n")

    print(f"WF aggregates: calmar_mean={mean_c:.3f}, calmar_cov_pct={cov_pct:.2f}%")

if __name__ == "__main__":
    main()
