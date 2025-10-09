#!/usr/bin/env python3
import argparse, yaml, pandas as pd, numpy as np, sys
from pathlib import Path

def _fetch_series_yf(symbol: str, start: str, end: str):
    try:
        import yfinance as yf
    except Exception as e:
        print(f"[ERROR] yfinance non installato: {e}", file=sys.stderr)
        return pd.Series(dtype="float64")
    try:
        df = yf.download(symbol, start=start, end=end, interval="1d", auto_adjust=False, progress=False)
        if df is None or df.empty:
            t = yf.Ticker(symbol)
            df = t.history(start=start, end=end, interval="1d", auto_adjust=False)
        if df is None or df.empty:
            print(f"[WARN] Nessun dato per {symbol}", file=sys.stderr)
            return pd.Series(dtype="float64")
        df = df.copy()
        col = "Adj Close" if "Adj Close" in df.columns else ("Close" if "Close" in df.columns else None)
        if col is None:
            try:
                df.columns = [" ".join([c for c in c if isinstance(c, str)]) if isinstance(c, tuple) else c for c in df.columns]
                col = "Adj Close" if "Adj Close" in df.columns else ("Close" if "Close" in df.columns else None)
            except Exception:
                pass
        if col is None:
            print(f"[WARN] Colonna Close/Adj Close assente per {symbol}", file=sys.stderr)
            return pd.Series(dtype="float64")
        s = pd.to_numeric(df[col], errors="coerce")
        s.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
        s.name = symbol
        return s.dropna()
    except Exception as e:
        print(f"[WARN] Errore fetch {symbol}: {e}", file=sys.stderr)
        return pd.Series(dtype="float64")

def build_regime(cfg: dict):
    start = str(cfg.get("start", "2018-01-01"))
    end = str(cfg.get("end", pd.Timestamp.today().date().isoformat()))
    vix_symbol = cfg.get("vix_symbol", "^VIX")
    smooth = int(cfg.get("smoothing_days", 5))

    vix = _fetch_series_yf(vix_symbol, start, end)
    if vix.empty:
        df = pd.DataFrame({"Date": [], "vix": [], "vix_smooth": [], "vix_z": [], "regime": []})
        return df

    vix_smooth = vix.rolling(smooth, min_periods=1).mean()
    roll = 252
    mu = vix_smooth.rolling(roll, min_periods=20).mean()
    sd = vix_smooth.rolling(roll, min_periods=20).std(ddof=0)
    z = (vix_smooth - mu) / (sd + 1e-12)
    regime = (vix_smooth < mu).astype(int)

    out = pd.DataFrame({
        "Date": vix_smooth.index,
        "vix": vix.values,
        "vix_smooth": vix_smooth.values,
        "vix_z": z.values,
        "regime": regime.values
    })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=False)
    ap.add_argument("--universe", required=False)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    cfg = {}
    if args.features and Path(args.features).exists():
        try:
            cfg = yaml.safe_load(open(args.features, "r", encoding="utf-8")) or {}
        except Exception as e:
            print(f"[WARN] Impossibile leggere {args.features}: {e}", file=sys.stderr)
            cfg = {}
    reg_cfg = (cfg.get("regime") or {}) if isinstance(cfg, dict) else {}
    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    df_reg = build_regime(reg_cfg if isinstance(reg_cfg, dict) else {})
    df_reg.to_csv(Path(args.outdir) / "regime.csv", index=False)
    print(f"[OK] regime.csv scritto con {len(df_reg)} righe")

if __name__ == "__main__":
    main()
