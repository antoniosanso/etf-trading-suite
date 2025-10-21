#!/usr/bin/env python3
import argparse, json, os
from pathlib import Path
import pandas as pd

QUESTIONS = [
  "Quanti ETF risultano nell'indice? (>= 200)",
  "Per ogni ETF, l'ultima data è entro gli ultimi 10 giorni di calendario?",
  "Sono presenti le colonne standard (Date,Ticker,Open,High,Low,Close,Volume,Currency) nello snapshot?",
  "Il modello ha prodotto output (files in outputs/)?",
  "La size del portafoglio attivo è entro i limiti previsti (1–3 posizioni)?",
  "Il drawdown non supera il kill-switch?",
  "Le regole di risk sizing sono state applicate (sizing dinamico > 0)?",
  "I report contengono ordini per la prossima seduta se ci sono segnali?"
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--eod", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    out_lines = []

    idx = json.loads(Path(args.index).read_text(encoding="utf-8"))
    count = int(idx.get("count", 0))
    out_lines.append(f"[Q1] ETF nell'indice: {count}  -> {'OK' if count>=200 else 'WARN'}")

    df = pd.read_csv(args.eod, parse_dates=["Date"])
    cols_ok = all(c in df.columns for c in ["Date","Ticker","Open","High","Low","Close","Volume","Currency"])
    out_lines.append(f"[Q3] Colonne standard snapshot: {'OK' if cols_ok else 'FAIL'}")
    if not df.empty:
        max_date = pd.to_datetime(df["Date"]).max()
        # Normalizza entrambi a naive UTC per confronto sicuro
        now_utc = pd.Timestamp.utcnow().tz_localize(None)
        max_naive = max_date.tz_localize(None) if getattr(max_date, "tzinfo", None) else max_date
        recent_ok = (now_utc - max_naive) <= pd.Timedelta(days=10)
        out_lines.append(f"[Q2] Ultima data {max_date.date()} (<=10 giorni): {'OK' if recent_ok else 'WARN'}")
    else:
        out_lines.append("[Q2] Snapshot vuoto: FAIL")

    report_dir = Path(args.report)
    outputs_ok = any(report_dir.rglob("*"))
    out_lines.append(f"[Q4] Output modello presenti: {'OK' if outputs_ok else 'FAIL'}")

    out_lines.append("[Q5] Size portafoglio: TBD (richiede parsing report)")
    out_lines.append("[Q6] Kill-switch DD: TBD (richiede parsing log)")
    out_lines.append("[Q7] Risk sizing>0: TBD (richiede parsing log/trades)")
    out_lines.append("[Q8] Ordini generati: TBD (richiede parsing ordini)")

    Path('latest/system_checks.txt').write_text("\n".join(out_lines), encoding="utf-8")

if __name__ == "__main__":
    main()
