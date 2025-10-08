import argparse, yaml, pandas as pd, sys, os
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.engine.backtest import run_backtest

ap = argparse.ArgumentParser()
ap.add_argument('--config', required=True, help='Path to model.yaml')
ap.add_argument('--data', default='data/eod.csv', help='Path to merged EOD CSV')
args = ap.parse_args()

with open(args.config, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

prices = pd.read_csv(args.data)
prices['Date'] = pd.to_datetime(prices['Date'])

result = run_backtest(prices, cfg)
print(result['kpis'])
