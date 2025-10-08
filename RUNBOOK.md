# RUNBOOK.md

## Aggiornare l’universo
1. Modifica `etf-trading-config/universe.csv` aggiungendo i ticker (una riga per ticker).
2. Commit su `main` → la prossima run scarica i dati automaticamente.

## Lanciare il workflow a mano
- `Actions → Backtest (CI via Web Ingest) → Run workflow`

## Dove leggere i risultati
- **KPI Backtest** → artifact `backtest-artifacts` (`kpis.json`, `summary.txt`, `equity_curve.csv`)
- **Walk-Forward** → `wf_report.json`, `wf_summary.txt`
- **Signals** → artifact `signals` (`entries_today.csv`, `watchlist_today.csv`, `summary.md`)
- **Operational** → artifact `operational-report` (`operational_report.md`)
- **Dataset** → artifact `eod-dataset` (`eod-latest.csv`, `.parquet`, `by_ticker/*.csv`, `summary.json`)

## Esecuzione locale (facoltativa)
```bash
python -m pip install -r etf-trading-engine/requirements.txt
python etf-trading-engine/scripts/download_eod_yf.py --universe etf-trading-config/universe.csv --output etf-trading-engine/data/eod.csv --start 2018-01-01 --threads 4 --adjusted
python etf-trading-engine/scripts/sanity_check.py --data etf-trading-engine/data/eod.csv
python etf-trading-engine/scripts/run_ci_backtest.py --config etf-trading-config/model.yaml --data etf-trading-engine/data/eod.csv --outdir outputs
python etf-trading-engine/scripts/walk_forward.py --config etf-trading-config/model.yaml --data etf-trading-engine/data/eod.csv --windows etf-trading-config/wf_windows.yaml --outdir outputs
python etf-trading-engine/scripts/signals.py --config etf-trading-config/signals.yaml --data etf-trading-engine/data/eod.csv --outdir outputs
python etf-trading-engine/scripts/operational_report.py --data etf-trading-engine/data/eod.csv --config etf-trading-config/operational.yaml --outdir outputs
```
