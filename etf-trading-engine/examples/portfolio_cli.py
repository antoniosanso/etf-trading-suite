import argparse, json
from pathlib import Path
import pandas as pd
from portfolio_tools import load_dataset, pivot_close, daily_returns, build_portfolio, kpis, corr_matrix

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', required=True, help='Path to eod-latest.csv')
    ap.add_argument('--weights', help='JSON mapping ticker->weight (e.g. {"SEME":0.25,...})')
    ap.add_argument('--corr', action='store_true', help='Print correlation matrix')
    args = ap.parse_args()

    df = load_dataset(args.dataset)
    px = pivot_close(df)
    rets = daily_returns(px)

    if args.weights:
        w = json.loads(args.weights)
        port = build_portfolio(rets, w)
        kp = kpis(port)
        print("PORTFOLIO KPIs", kp)

    if args.corr:
        print(corr_matrix(rets))

if __name__ == '__main__':
    main()
