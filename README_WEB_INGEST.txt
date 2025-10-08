Web Ingest Upgrade
------------------
Questo pacchetto sostituisce il datalake con un download diretto da Yahoo Finance.
Carica i file mantenendo la stessa struttura (sovrascrivi .github/workflows/backtest.yml e aggiungi scripts/download_eod_yf.py).

Il workflow userà i ticker presenti in etf-trading-config/universe.csv.
Per espandere l'universo, aggiungi righe a universe.csv (colonna 'Ticker') e fai Commit: il CI scaricherà i nuovi dati automaticamente.
