#!/usr/bin/env python3
# Operational report generator (robusto e con fallback)
# Usage:
#   python operational_report.py --data etf-trading-engine/data/eod.csv \
#       --config etf-trading-config/operational.yaml \
#       --outdir outputs
import argparse, pandas as pd, numpy as np, json, sys, os
from pathlib import Path
from datetime import datetime, timezone

def safe_read_csv(path, **kwargs):
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, **kwargs)
    except Exception:
        # prova senza low_memory
        try:
            return pd.read_csv(p, low_memory=False)
        except Exception as e:
            print(f"[WARN] Impossibile leggere {p}: {e}", file=sys.stderr)
            return pd.DataFrame()

def last_date(df):
    if 'Date' not in df.columns or df.empty:
        return None
    try:
        d = pd.to_datetime(df['Date'], errors='coerce')
        d = d.dropna()
        return None if d.empty else d.max()
    except Exception:
        return None

def regime_summary(features_dir: Path):
    reg = safe_read_csv(features_dir / "regime.csv")
    if reg.empty:
        return {"has_regime": False}
    try:
        reg['Date'] = pd.to_datetime(reg['Date'], errors='coerce')
        reg = reg.sort_values('Date').dropna(subset=['Date'])
        last = reg.iloc[-1].to_dict()
        return {
            "has_regime": True,
            "vix": float(last.get('vix', np.nan)) if pd.notna(last.get('vix', np.nan)) else None,
            "vix_z": float(last.get('vix_z', np.nan)) if pd.notna(last.get('vix_z', np.nan)) else None,
            "regime": int(last.get('regime', 0)) if pd.notna(last.get('regime', np.nan)) else 0
        }
    except Exception as e:
        print(f"[WARN] regime.csv non parsabile: {e}", file=sys.stderr)
        return {"has_regime": False}

def simple_drawdown(eod: pd.DataFrame):
    """Stima media drawdown attuale per ticker (fallback, non usata per KPI)."""
    needed = {'Date','Ticker','Close'}
    if eod.empty or not needed.issubset(set(eod.columns)):
        return None
    try:
        eod['Date'] = pd.to_datetime(eod['Date'], errors='coerce')
        eod = eod.dropna(subset=['Date','Ticker','Close'])
        dd_list = []
        for t, g in eod.groupby('Ticker', sort=False):
            g = g.sort_values('Date')
            rolling_max = g['Close'].cummax()
            dd = (g['Close'] / rolling_max - 1.0)
            if not dd.empty:
                dd_list.append(float(dd.iloc[-1]))
        if not dd_list:
            return None
        return float(np.mean(dd_list))
    except Exception as e:
        print(f"[WARN] drawdown fallback errore: {e}", file=sys.stderr)
        return None

def load_signals(outputs_dir: Path):
    entries = safe_read_csv(outputs_dir / "signals" / "entries_today.csv")
    # normalizza nomi colonna frequenti
    colmap = {
        'entry':'Entry','stop':'Stop','tp':'TP1','tp1':'TP1','tp_1':'TP1',
        'tp2':'TP2','size':'Size','reason':'Reason','ticker':'Ticker'
    }
    if not entries.empty:
        entries.columns = [colmap.get(c.strip().lower(), c) for c in entries.columns]
        # Keep only expected columns if present
        keep = [c for c in ['Ticker','Entry','Stop','TP1','TP2','Size','Reason'] if c in entries.columns]
        entries = entries[keep]
    return entries

def md_table(df: pd.DataFrame, max_rows=5):
    if df.empty:
        return "_Nessun segnale per oggi._\n"
    df2 = df.head(max_rows).copy()
    # round numerici se possibile
    for c in df2.columns:
        if pd.api.types.is_numeric_dtype(df2[c]):
            df2[c] = df2[c].round(4)
    header = "| " + " | ".join(df2.columns) + " |"
    sep = "| " + " | ".join(["---"]*len(df2.columns)) + " |"
    rows = ["| " + " | ".join(str(x) for x in row) + " |" for row in df2.to_numpy()]
    return "\n".join([header, sep] + rows) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="CSV EOD (Date,Ticker,Open,High,Low,Close,Volume...)")
    ap.add_argument("--config", required=False, help="operational.yaml (opzionale)")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    eod = safe_read_csv(args.data, low_memory=False)
    last_dt = last_date(eod)
    universe_n = int(eod['Ticker'].nunique()) if 'Ticker' in eod.columns and not eod.empty else 0

    # regime / sentiment (se presenti)
    features_dir = Path("features")
    reg = regime_summary(features_dir)

    # segnali
    entries = load_signals(Path(outdir))

    # drawdown medio (fallback)
    dd_avg = simple_drawdown(eod)

    # P&L atteso ciclo: se in entries c'è Size e (TP1,Stop,Entry), calcolo payoff medio semplice
    expected_cycle = None
    try:
        if not entries.empty and {'Entry','Stop','TP1'}.issubset(set(entries.columns)):
            r = (entries['TP1'].astype(float) - entries['Entry'].astype(float)).abs()
            risk = (entries['Entry'].astype(float) - entries['Stop'].astype(float)).abs()
            payoff = (r / risk.replace(0, np.nan)).fillna(0)
            expected_cycle = float(payoff.mean())
    except Exception:
        expected_cycle = None

    # Compose Markdown
    ts_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = []
    md.append(f"# Operational Report — {ts_utc}\n")
    md.append(f"- Universe: **{universe_n}** ticker")
    if last_dt is not None:
        md.append(f"- Ultima data EOD: **{last_dt.date()}**")
    if reg.get("has_regime"):
        regime_tag = "Risk-ON ✅" if reg.get("regime",0)==1 else "Risk-OFF ⚠️"
        md.append(f"- Regime: **{regime_tag}** · VIX z ≈ {reg.get('vix_z')}")
    if dd_avg is not None:
        md.append(f"- Drawdown medio corrente (fallback): **{round(dd_avg*100,2)}%**")
    md.append("")
    md.append("## Segnali di oggi (Top 5)\n")
    md.append(md_table(entries, max_rows=5))
    md.append("")
    if expected_cycle is not None:
        md.append(f"**Payoff medio atteso (TP1/Stop) sulle proposte di oggi:** ~{expected_cycle:.2f}x\n")
    md_text = "\n".join(md).strip() + "\n"

    # Write outputs
    (outdir / "operational_report.md").write_text(md_text, encoding="utf-8")

    summary = {
        "ts_utc": ts_utc,
        "universe": universe_n,
        "last_eod_date": str(last_dt.date()) if last_dt is not None else None,
        "regime": reg,
        "drawdown_avg": dd_avg,
        "signals_rows": int(entries.shape[0]) if not entries.empty else 0,
        "payoff_mean_estimate": expected_cycle
    }
    (outdir / "operational_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("[OK] operational_report.md scritto")

if __name__ == "__main__":
    main()
