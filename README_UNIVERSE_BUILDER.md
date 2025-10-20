# Aggiunta consigliata al workflow (step prima del merge/backtest):
# - name: Build/refresh universe (>=200 ETFs)
#   run: |
#     python etf-trading-engine/scripts/build_universe.py --min 220 --venues "Borsa Italiana,Euronext Paris,Euronext Amsterdam"
