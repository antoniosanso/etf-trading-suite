PATCH: Guardrails non-blocking
Data: 20251009_123349 UTC

Cosa cambia
- Lo step "Guardrails" non blocca più la pipeline quando il verdetto è RED.
- Il verdetto è comunque salvato in outputs/guardrails_status.json e mostrato nei log.
- Viene esportata la variabile di ambiente GUARDRAILS_EXIT (0=GREEN, 2=YELLOW, 3=RED).

Istruzioni
1) Estrai lo zip.
2) Carica il file .github/workflows/trading_suite.yml nel repo etf-trading-suite sovrascrivendo il precedente.
3) Commit directly to main.
4) Actions → Trading Suite — Unified Daily → Run workflow.
