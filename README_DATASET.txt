EOD Dataset Publisher & Portfolio Tools
--------------------------------------
- Aggiunge un workflow 'EOD Dataset Publisher' che, ogni giorno alle 06:15 Europe/Rome, scarica i prezzi via web per tutti i ticker di `etf-trading-config/universe.csv`, valida e pubblica gli artifact:
  - dataset/eod-latest.csv
  - dataset/eod-latest.parquet
  - dataset/by_ticker/*.csv
  - dataset/summary.json
- Include strumenti semplici per analisi di portafoglio: `portfolio_tools.py` e `examples/portfolio_cli.py`.
