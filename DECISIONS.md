# DECISIONS.md

Registro decisioni chiave (data ↓).

- **[2025-10-08] Ingestion web (Yahoo)** — sostituisce datalake locale. Normalizzazione date `utc=True` → tz-naive. Dedup su `(Ticker,Date)`.
- **[2025-10-08] Guardrails “rigidi + YELLOW”** — soglie invariate; se valore entro ±10% o WF incompleto → YELLOW, altrimenti RED.
- **[2025-10-08] Walk-Forward annuale + trimmed CoV** — finestre annuali; `wf_trim=1` (ignora best/worst) e soglia CoV 30%.
- **[2025-10-08] Signals & Operational report** — breakout 52w +0.3%, SL −7%, TP +14%, p(win)=45%; LT SWDA/TNOW con trailing.
- **Universo** — esteso (US core + UCITS LSE/Xetra); ampliamento a lotti curati per stabilità WF; liquidità min (ADV/Volume).
