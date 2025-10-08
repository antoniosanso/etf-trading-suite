# ETF Trading Suite (v4.1)

Suite pronta per GitHub con:
- **Engine** (motore di backtest)
- **Config** (parametri, universo, schedule)
- **CI** (GitHub Actions: merge dati → backtest → artifact KPI)

Datalake usato in read‑only: `antoniosanso/etf-datalake`

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
   Al termine scarica l’artifact **backtest-artifacts** (KPIs + equity curve).

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

> Nota: se il datalake GitHub è **privato**, il workflow richiederà PAT/token. Se è pubblico, parte subito.
