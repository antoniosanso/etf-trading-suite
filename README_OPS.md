# ETF Trading Suite — README_OPS

**Obiettivo:** automatizzare ingest dati, backtest + walk-forward, guardrail decisionali, generazione segnali operativi (entry/stop/TP/size) e report operativo giornaliero.

## Architettura (alto livello)
- **Ingestion Web** (Yahoo Finance) → `etf-trading-engine/scripts/download_eod_yf.py`  
  Output: `etf-trading-engine/data/eod.csv`
- **Dataset Publisher** → artifact giornalieri: `dataset/eod-latest.csv`, `.parquet`, `by_ticker/*.csv`, `summary.json`
- **Backtest (CI)** → sanity → backtest → walk-forward → guardrails → artifact KPI
- **Signals** → `outputs/signals/{entries_today.csv,watchlist_today.csv,summary.md}`
- **Operational report** → `outputs/operational_report.md` (tabella come nello screenshot)

## Workflow (GitHub Actions)
- `Backtest (CI via Web Ingest)` (cron: ~06:00 CET)
  1. Download EOD (web) → Sanity
  2. Backtest CI (`model.yaml`)
  3. Walk-Forward (`wf_windows.yaml`)
  4. Generate Signals (`signals.yaml`)
  5. Operational report (`operational.yaml`)
  6. Guardrails (soglie rigide + status YELLOW per borderline/NaN)
  7. Upload artifacts (KPI, WF, signals, report)
- `EOD Dataset Publisher` (cron: ~06:15 CET) → esporta dataset pulito

## Guardrails (rigidi + YELLOW per borderline)
- **Sharpe ≥ 0.30**
- **ProfitFactor ≥ 1.10**
- **|MaxDD| ≤ 35%**
- **WF Calmar CoV ≤ 30%** (trimmed, ignora best/worst, `wf_trim: 1`)
- Se il valore è entro ±10% dalla soglia o WF è incompleto (`NaN`) → **YELLOW**
- Violazioni nette → **RED** (exit code≠0)

## Report Operativo (giornaliero)
- **Trading (cap. per ciclo)**: 52w breakout +0.3%, SL −7%, TP +14%, p(win)=45% → mostra Ticker/Quantità/Entrata/Stop/TP/Ultimo/P&L atteso per linea e **Totale ciclo**.
- **Lungo Termine**: pesi target (es. SWDA 60% + TNOW 40%), trailing stop e P&L atteso 12m.

## Dove stanno i file chiave
- `etf-trading-config/model.yaml` — parametri motore + `stop_criteria`
- `etf-trading-config/signals.yaml` — regole per segnali e sizing
- `etf-trading-config/operational.yaml` — layout/parametri del report operativo
- `etf-trading-config/wf_windows.yaml` — finestre Walk-Forward

Mettere questo `README_OPS.md`, `DECISIONS.md` e `RUNBOOK.md` **alla radice del repo** e allegarli anche nel **Project “Investimenti”** come reference.
