# ETF Trading Suite — Unified Automation Patch

Questa patch unifica e amplia tutte le capacità richieste:
- **Universe Snapshot**: conteggio titoli, duplicati, lista normalizzata (artifact JSON/CSV).
- **Public Status Poster**: Issue pubblica con ancora univoca + KPI integrati (se presenti).
- **Content Indexer**: indice completo del repo, sommari file chiave, pubblicazione su GitHub Pages.
- **Content Mirror**: mirror selettivo di file testuali come artifact per consumo esterno.
- **Generic Fetcher**: scarica pattern arbitrari di file dal repo in `outputs/mirror`.

## Workflows inclusi
- `.github/workflows/universe_fetch.yml`
- `.github/workflows/status_poster.yml`
- `.github/workflows/content_index.yml`
- `.github/workflows/content_mirror.yml`

## Script inclusi
- `etf-trading-engine/scripts/fetch_universe.py`
- `etf-trading-engine/scripts/generate_status.py`
- `etf-trading-engine/scripts/kpi_aggregator.py`
- `etf-trading-engine/scripts/index_repo.py`
- `etf-trading-engine/scripts/fetch_file.py`

## Setup rapido
1. Unzip nella root del repo mantenendo i percorsi.
2. (Se non già fatto) abilita **GitHub Pages** → “Build and deployment: GitHub Actions”.
3. Esegui manualmente:
   - **Universe Snapshot**
   - **Public Status Poster**
   - **Content Indexer**
   - **Content Mirror**

Dopo il primo run:
- Troverai una Issue “**ETF-TRADING-SUITE PUBLIC STATUS ANCHOR 9E1F2C — Live Status**” con:
  - numero di **ticker unici**, duplicati
  - KPI (Sharpe, PF, MaxDD, WF Calmar CoV) se disponibili
- `docs/CONTENT_INDEX.md` mostrerà **tutti i file** con link blob/raw e excerpt.
- Gli artifact `repo-index`, `repo-mirror`, `public-status`, `universe-snapshot` saranno disponibili per download.

## Estensioni (facoltative)
- Agganciare i workflow di backtest per scrivere KPI in `outputs/backtest/kpis.json` e `outputs/wf/wf_report.json` così lo **Status Poster** mostra sempre i numeri aggiornati.
- Fail-fast se `duplicate_rows > 0` nel Universe Snapshot.
- Aggiungere badge nel README che puntano alla Issue “Live Status” e a `docs/CONTENT_INDEX.md`.
