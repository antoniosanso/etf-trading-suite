# RUNBOOK.md

## Aggiornare l’universo
- Edit `etf-trading-config/universe.csv` → commit → la prossima run scarica i nuovi ticker.

## Lanciare i workflow
- Actions → **Backtest (CI via Web Ingest)** → Run workflow
- Actions → **EOD Dataset Publisher** → Run workflow

## Leggere i risultati
- KPI: artifact `backtest-artifacts`
- WF: `wf_report.json`, `wf_summary.txt`
- Signals: artifact `signals`
- Report operativo: artifact `operational-report`
- Dataset: artifact `eod-dataset` **e** nel repo **datalake/latest/**

## Pubblicazione nel datalake
Richiede secret `DATASINK_TOKEN` (PAT con scope `repo`) nel repo *trading-suite*.
