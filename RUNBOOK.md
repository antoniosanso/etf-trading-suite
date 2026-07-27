# RUNBOOK.md

## Aggiornare l’universo
- Modificare `universe.csv` nel repository `etf-datalake`.
- Allineare poi `etf-trading-config/universe.csv` nella suite.
- La run del datalake verifica duplicati, dati disponibili, copertura e freschezza.

## Lanciare i workflow
- Datalake → Actions → **Update validated ETF universe**
- Trading Suite → Actions → **Trading suite from validated datalake**

## Leggere i risultati
- KPI: artifact `backtest-artifacts`
- WF: `wf_report.json`, `wf_summary.txt`
- Signals: artifact `signals`
- Report operativo: artifact `operational-report`
- Dataset: artifact `eod-dataset` **e** nel repo **datalake/latest/**

## Controllo universo
Aprire `latest/quality-report.json` nel datalake. `status` deve essere `pass`,
`valid_count` almeno 96 e ogni esclusione deve riportare una motivazione.
