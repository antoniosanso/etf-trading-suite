# ETF Trading Suite (v4.1)

Suite pronta per GitHub con:
- **Engine** (motore di backtest)
- **Config** (parametri, universo, schedule)
- **CI** (GitHub Actions: merge dati → backtest → artifact KPI)

Datalake usato in read-only: `antoniosanso/etf-datalake`

## Documentazione operativa obbligatoria

Prima di modificare strategie, interpretare segnali o formulare indicazioni su denaro reale, leggere nell'ordine:

1. [`README_OPS.md`](README_OPS.md) — contesto, stato operativo e gerarchia delle fonti;
2. [`DECISIONS.md`](DECISIONS.md) — decisioni attive, regole superate e correzioni;
3. [`RUNBOOK.md`](RUNBOOK.md) — controlli obbligatori su posizione, dati, livelli, rischio e calcoli.

I segnali e i guardrail della suite sono input analitici e non equivalgono a un ordine eseguibile. In caso di conflitto, prevalgono le decisioni più recenti registrate in `DECISIONS.md`.

## Come pubblicare su GitHub (Windows, 2 minuti)
1) Apri **Prompt dei comandi** nella cartella di questa suite.
2) Copia e incolla, **una riga alla volta**:
```
git init
git add .
git commit -m "init suite v4.1 (engine+config+CI)"
git branch -M main
git remote add origin https://github.com/antoniosanso/etf-trading-suite.git
git push -u origin main
```
3) Su GitHub → tab **Actions** → workflow “Backtest (CI)”.
   Al termine scarica l'artifact **backtest-artifacts** (KPI + equity curve).

## Esecuzione locale (facoltativa)
```
cd etf-trading-engine
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

# merge CSV dal datalake locale (cartella sorella etf-datalake)
python scripts\merge_eod.py --datalake ..\etf-datalake --output data\eod.csv --recursive --datecol dt --closecol close --tickercol ticker --opencol open --highcol high --lowcol low --volumecol volume

# backtest locale
python examples\run_backtest.py --config ..\etf-trading-config\model.yaml --data data\eod.csv
```

## Dashboard operativo

La dashboard riunisce segnali, posizioni, KPI, confronto con benchmark e buy-and-hold
e genera un piano operativo dimensionato per il rischio. Commissioni Fineco, spread e
aliquota fiscale sono modificabili perché dipendono dal profilo e dalla posizione del cliente.

```bash
cd etf-trading-engine
streamlit run dashboard.py
```

La dashboard legge gli artefatti dalla cartella `outputs/` (modificabile nella barra
laterale): `signals/entries_today.csv`, `positions.csv`, `kpis.json` ed
`equity_curve.csv`. Quest'ultimo può contenere le colonne `Date`, `Strategy`,
`Benchmark` e `BuyHold`.

> Nota: se il datalake GitHub è **privato**, il workflow richiederà PAT/token. Se è pubblico, parte subito.
