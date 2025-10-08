import argparse, json, yaml
import pandas as pd
from pathlib import Path
from src.engine.backtest import run_backtest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--data', required=True)
    ap.add_argument('--outdir', required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, 'r', encoding='utf-8'))
    prices = pd.read_csv(args.data)
    prices['Date'] = pd.to_datetime(prices['Date'], utc=True).dt.tz_localize(None)

    res = run_backtest(prices, cfg)
    kpis = res['kpis']

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    (outdir / 'kpis.json').write_text(json.dumps(kpis, indent=2), encoding='utf-8')
    pd.DataFrame({'Equity': res['equity_curve']}).to_csv(outdir / 'equity_curve.csv', index=False)

    with open(outdir / 'summary.txt', 'w', encoding='utf-8') as f:
        f.write("KPIs (CI Backtest)\n")
        for k,v in kpis.items():
            f.write(f"- {k}: {v}\n")

    print("✅ Backtest completato. Artifact in 'outputs/'.")

if __name__ == "__main__":
    main()
