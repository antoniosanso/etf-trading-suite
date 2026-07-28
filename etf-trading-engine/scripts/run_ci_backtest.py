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

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    res = run_backtest(prices, cfg)
    if 'runs' in res:
        # active_run=all is useful for research; keep one stable artifact per run.
        all_trades, all_orders = [], []
        for name, run in res['runs'].items():
            (outdir / f'kpis_{name}.json').write_text(
                json.dumps(run['kpis'], indent=2), encoding='utf-8')
            for trade in run.get('trades', []):
                all_trades.append({**trade, 'Run': name})
            for order in run.get('orders', []):
                all_orders.append({**order, 'Run': name})
        kpis = {name: run['kpis'] for name, run in res['runs'].items()}
        equity_curve = []
        trades, orders = all_trades, all_orders
    else:
        kpis = res['kpis']
        equity_curve = res['equity_curve']
        trades, orders = res.get('trades', []), res.get('orders', [])

    (outdir / 'kpis.json').write_text(json.dumps(kpis, indent=2), encoding='utf-8')
    if 'curves' in res:
        res['curves'].to_csv(outdir / 'equity_curve.csv', index=False)
    else:
        pd.DataFrame({'Equity': equity_curve}).to_csv(
            outdir / 'equity_curve.csv', index=False)
    pd.DataFrame(trades).to_csv(outdir / 'trades.csv', index=False)
    signals_dir = outdir / 'signals'; signals_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(orders).to_csv(
        signals_dir / 'entries_today.csv', index=False)
    (outdir / 'data_quality.json').write_text(
        json.dumps(res.get('data_quality', {}), indent=2), encoding='utf-8')

    with open(outdir / 'summary.txt', 'w', encoding='utf-8') as f:
        f.write("KPIs (CI Backtest)\n")
        for k,v in kpis.items():
            f.write(f"- {k}: {v}\n")

    print("✅ Backtest completato. Artifact in 'outputs/'.")

if __name__ == "__main__":
    main()
