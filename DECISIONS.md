# DECISIONS.md

- **[2025-10-08] Ingestion web (Yahoo)**; normalizzazione date tz-naive; dedup `(Ticker,Date)`.
- **[2025-10-08] Guardrails “rigidi + YELLOW”**; soglie invariate, borderline/NaN ⇒ YELLOW.
- **[2025-10-08] WF annuale + trimmed CoV** (`wf_trim:1`, soglia 30%).
- **[2025-10-08] Signals & Operational report** (breakout 52w, SL −7%, TP +14%, p=45%); LT SWDA/TNOW.
- **[2025-10-08] Pubblicazione dataset nel datalake** → cartella `latest/` su https://github.com/antoniosanso/etf-datalake.
