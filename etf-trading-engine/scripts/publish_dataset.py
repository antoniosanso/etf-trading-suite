import argparse, json
from pathlib import Path
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--outdir', required=True)
    args = ap.parse_args()

    inp = Path(args.input)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(inp)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date','Close']).sort_values(['Ticker','Date'])

    # Save CSV and Parquet
    csv_path = outdir / 'eod-latest.csv'
    pq_path = outdir / 'eod-latest.parquet'
    df.to_csv(csv_path, index=False)
    try:
        df.to_parquet(pq_path, index=False)
    except Exception as e:
        print(f"⚠️ Parquet non disponibile: {e}")

    # Per-ticker CSV (per usi rapidi)
    bt_dir = outdir / 'by_ticker'
    bt_dir.mkdir(exist_ok=True)
    for t, d in df.groupby('Ticker'):
        d.to_csv(bt_dir / f'{t}.csv', index=False)

    # Summary JSON
    summary = {
        "rows": int(len(df)),
        "tickers": int(df['Ticker'].nunique()),
        "date_min": str(df['Date'].min().date() if not df.empty else None),
        "date_max": str(df['Date'].max().date() if not df.empty else None),
        "columns": list(df.columns),
    }
    with open(outdir / 'summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"✅ Dataset pronto: {csv_path} | {pq_path}")

if __name__ == '__main__':
    main()
