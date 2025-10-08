# Istruzioni per la pubblicazione nel datalake

1) Su https://github.com/antoniosanso/etf-trading-suite vai su **Settings → Secrets and variables → Actions** → **New repository secret**  
   - Name: `DATASINK_TOKEN`  
   - Value: *Personal Access Token* (scope **repo**) del tuo account

2) Verifica che https://github.com/antoniosanso/etf-datalake abbia branch `main` e che tu abbia permessi di push.

3) Carica questo workflow (`.github/workflows/dataset.yml`) nel repo *trading-suite* e lancialo da **Actions**.

Il job copierà ogni mattina i file in `etf-datalake/latest/`:
- `eod-latest.csv`
- `eod-latest.parquet` (se disponibile)
- `summary.json`
- CSV per-ticker nella cartella `by_ticker/` (solo come artifact, non nel datalake per evitare gonfiaggio del repo).
