import argparse, json
import pandas as pd
import yaml
from src.engine.backtest import run_backtest
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--data', required=True)
    ap.add_argument('--outdir', required=True)
    args = ap.parse_args()

    with open(args.config, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    prices = pd.read_csv(args.data)
    prices['Date'] = pd.to_datetime(prices['Date'])

    res = run_backtest(prices, cfg)
    kpis = res['kpis']

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    with open(outdir / 'kpis.json', 'w', encoding='utf-8') as f:
        json.dump(kpis, f, indent=2)

    eq = pd.DataFrame({'Equity': res['equity_curve']})
    eq.to_csv(outdir / 'equity_curve.csv', index=False)

    with open(outdir / 'summary.txt', 'w', encoding='utf-8') as f:
        f.write("KPIs (CI Backtest)\n")
        for k,v in kpis.items():
            f.write(f"- {k}: {v}\n")

    print("✅ Backtest completato. Artifact in 'outputs/'.")

if __name__ == "__main__":
    main()
