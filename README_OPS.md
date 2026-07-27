# ETF Trading Suite — README_OPS

**Obiettivo:** ingest web, backtest+WF, guardrail, **segnali operativi** e **report operativo** giornaliero.

## Repos
- **Trading Suite**: https://github.com/antoniosanso/etf-trading-suite
- **Datalake (dataset pubblicati)**: https://github.com/antoniosanso/etf-datalake

## Architettura
- **Ingestion Web** nel datalake → download e validazione di almeno 96 ETF
- **Quality gate** → `latest/quality-report.json`; il flusso si ferma se validità,
  completezza o aggiornamento non rispettano le soglie
- **Trading Suite** → legge soltanto gli storici validati dal datalake
- **Backtest (CI)** → sanity → backtest → walk-forward → guardrails → artifact KPI
- **Signals** → `outputs/signals/{entries_today.csv,watchlist_today.csv,summary.md}`
- **Operational report** → `outputs/operational_report.md` (tabella operativa)

## Workflow principali
- Datalake: `Update validated ETF universe` (giorni feriali)
- Trading Suite: `Trading suite from validated datalake`, eseguito dopo il datalake

## Guardrails (rigidi + YELLOW per borderline)
- Sharpe ≥ 0.30 · ProfitFactor ≥ 1.10 · |MaxDD| ≤ 35% · WF Calmar CoV ≤ 30% (trimmed, `wf_trim:1`)
- Borderline (±10%) o WF incompleto ⇒ **YELLOW**; violazione netta ⇒ **RED**.

## File chiave
`etf-trading-config/model.yaml`, `signals.yaml`, `operational.yaml`, `wf_windows.yaml`

> Questo documento va tenuto **alla radice** del repo *trading-suite* e allegato al Project “Investimenti”.
