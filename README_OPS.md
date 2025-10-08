# ETF Trading Suite — README_OPS

**Obiettivo:** ingest web, backtest+WF, guardrail, **segnali operativi** e **report operativo** giornaliero.

## Repos
- **Trading Suite**: https://github.com/antoniosanso/etf-trading-suite
- **Datalake (dataset pubblicati)**: https://github.com/antoniosanso/etf-datalake

## Architettura
- **Ingestion Web** (Yahoo Finance) → `etf-trading-engine/scripts/download_eod_yf.py` → `etf-trading-engine/data/eod.csv`
- **Dataset Publisher** → artifact + pubblicazione su **datalake/latest/** (`eod-latest.csv`, `.parquet`, `summary.json`)
- **Backtest (CI)** → sanity → backtest → walk-forward → guardrails → artifact KPI
- **Signals** → `outputs/signals/{entries_today.csv,watchlist_today.csv,summary.md}`
- **Operational report** → `outputs/operational_report.md` (tabella operativa)

## Workflow principali
- `Backtest (CI via Web Ingest)` (cron: ~06:00 CET)
- `EOD Dataset Publisher` (cron: ~06:15 CET) → **pubblica nel datalake**

## Guardrails (rigidi + YELLOW per borderline)
- Sharpe ≥ 0.30 · ProfitFactor ≥ 1.10 · |MaxDD| ≤ 35% · WF Calmar CoV ≤ 30% (trimmed, `wf_trim:1`)
- Borderline (±10%) o WF incompleto ⇒ **YELLOW**; violazione netta ⇒ **RED**.

## File chiave
`etf-trading-config/model.yaml`, `signals.yaml`, `operational.yaml`, `wf_windows.yaml`

> Questo documento va tenuto **alla radice** del repo *trading-suite* e allegato al Project “Investimenti”.
