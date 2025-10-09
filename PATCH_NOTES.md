PATCH: Rimozione completa del workflow legacy 'EOD Dataset Publisher'
Data: 20251009_125441 UTC

Cosa fa questo patch
- Aggiunge un workflow 'Cleanup — Remove legacy EOD publisher' che, quando lanciato, elimina
  i file workflow legacy dal repo **e poi si auto-elimina**.

Istruzioni
1) Carica nel repo `etf-trading-suite` il file `.github/workflows/remove_legacy_eod.yml` contenuto in questo zip (Upload files → Commit directly to main).
2) Vai su **Actions → Cleanup — Remove legacy EOD publisher → Run workflow**.
3) Al termine, il job rimuoverà:
   - `.github/workflows/build-and-publish.yml` (e varianti), ed eventuali alias tipo `eod_publisher*.yml`
   - **e si rimuoverà anche da solo** (`remove_legacy_eod.yml`).
4) Verifica in **Code → .github/workflows/** che restino solo i workflow che vuoi tenere
   (es: *Trading Suite — Unified Daily*).

Note
- Il branch di default usato è `main`. Se il repo usa un altro branch predefinito, dimmelo e preparo una versione ad hoc.
