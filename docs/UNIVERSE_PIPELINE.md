# Universe Pipeline

Questa pipeline aggiunge un job autonomo per **scaricare e validare** `etf-trading-config/universe.csv` e pubblicare uno **snapshot** come artifact.

## File
- `etf-trading-engine/scripts/fetch_universe.py`
- `.github/workflows/universe_fetch.yml`

## Come funziona
1. Esegue lo script in Python (richiede `requests`).
2. Stampa un **riepilogo** in log (righe totali, unici, duplicati, sample).
3. Carica come artifact:
   - `outputs/universe/universe_snapshot.csv`
   - `outputs/universe/universe_snapshot.json` (contiene anche la lista dei ticker).

## Perché è utile
- Consente ad altri workflow (e a te) di consumare uno **snapshot normalizzato** senza aprire il file raw.
- È un punto unico per rilevare **duplicati** o righe non valide.

## Estensioni suggerite
- Aggiungere una dipendenza dei workflow di backtest in modo che raccolgano questo artifact prima di girare.
- Fail-fast se `duplicate_rows > 0` (basta fare `jq` sulla chiave e exit 1).
