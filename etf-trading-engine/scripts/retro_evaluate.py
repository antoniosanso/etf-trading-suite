#!/usr/bin/env python3
import argparse, pandas as pd, numpy as np, os
from pathlib import Path

def find_col(df, names):
    for n in names:
        if n in df.columns: return n
        for c in df.columns:
            if c.lower() == n.lower(): return c
    return None

ap = argparse.ArgumentParser()
ap.add_argument("--as_of", required=True)
ap.add_argument("--signals", required=True)
ap.add_argument("--eod_full", required=True)
ap.add_argument("--universe", required=False)
ap.add_argument("--slippage_bps", default="5")
ap.add_argument("--outdir", required=True)
args = ap.parse_args()

Path(args.outdir).mkdir(parents=True, exist_ok=True)

s = pd.read_csv(args.signals)
if s.empty:
    Path(args.outdir, "summary.md").write_text("# Nessun segnale alla data as-of.\n")
    raise SystemExit(0)

ticker_col = find_col(s, ["Ticker","Symbol","ticker","symbol"])
entry_col  = find_col(s, ["Entry","Entrata (buy-stop)","entry"])
stop_col   = find_col(s, ["Stop","stop"])
tp_col     = find_col(s, ["TP","tp","TakeProfit","take_profit"])
h_min_col  = find_col(s, ["HorizonMin","hmin","h_min"])
h_max_col  = find_col(s, ["HorizonMax","hmax","h_max"])

if not all([ticker_col,entry_col,stop_col,tp_col]):
    raise SystemExit("Segnali: colonne minime mancanti (Ticker/Entry/Stop/TP).")

s["H_min"] = s[h_min_col] if h_min_col else 20.0
s["H_max"] = s[h_max_col] if h_max_col else 60.0
s = s.rename(columns={ticker_col:"Ticker", entry_col:"Entry", stop_col:"Stop", tp_col:"TP"})
for c in ["Entry","Stop","TP","H_min","H_max"]:
    s[c] = s[c].astype(float)

# Universe (per cluster)
u = None
if args.universe and os.path.exists(args.universe):
    try:
        u = pd.read_csv(args.universe)
        tcol = find_col(u, ["Ticker","Symbol","ticker","symbol"])
        ccol = find_col(u, ["Class","Category","AssetClass","class","category","asset_class"])
        if tcol: u = u.rename(columns={tcol:"Ticker"})
        if ccol: u = u.rename(columns={ccol:"AssetClass"})
        else:    u["AssetClass"] = "NA"
        u = u[["Ticker","AssetClass"]].drop_duplicates()
    except Exception:
        u = None

e = pd.read_csv(args.eod_full)
date_col = next((c for c in e.columns if c.lower() in ("date","dt","time")), None)
close_col = next((c for c in e.columns if c.lower() in ("close","adj_close","adjclose")), None)
tick_col  = next((c for c in e.columns if c.lower() in ("ticker","symbol")), None)
if any(x is None for x in [date_col, close_col, tick_col]):
    raise SystemExit("EOD: colonne minime mancanti (Date/Close/Ticker).")
e[date_col] = pd.to_datetime(e[date_col])
asof = pd.to_datetime(args.as_of)

slip = float(args.slippage_bps)/10000.0  # bps->fraction

rows = []
for _, r in s.iterrows():
    t = r["Ticker"]
    df = e[e[tick_col]==t].copy()
    if df.empty:
        rows.append({**r.to_dict(),"PnL_real_%":np.nan,"BH_ret_%":np.nan,"note":"no EOD"}); continue
    df = df.sort_values(date_col)
    df2 = df[df[date_col] >= asof].copy()
    if df2.empty:
        rows.append({**r.to_dict(),"PnL_real_%":np.nan,"BH_ret_%":np.nan,"note":"no future data"}); continue

    entry_price = r["Entry"]
    trig = df2[df2[close_col] >= entry_price]
    if trig.empty:
        rows.append({**r.to_dict(),"PnL_real_%":0.0,"BH_ret_%":0.0,"note":"non entrato"}); continue
    entry_day = trig.iloc[0][date_col]

    after = df[df[date_col] >= entry_day].reset_index(drop=True)
    if len(after) <= int(r["H_min"]):
        rows.append({**r.to_dict(),"PnL_real_%":np.nan,"BH_ret_%":np.nan,"note":"orizzonte incompleto"}); continue
    horizon_end = after.iloc[int(r["H_min"])][date_col]

    entry_close = after.iloc[0][close_col]*(1+slip)
    exit_close  = after.iloc[int(r["H_min"])][close_col]*(1-slip)
    pnl_real = (exit_close/entry_close - 1.0)*100.0

    exp_ret = (r["TP"]/entry_price - 1.0)*100.0*0.45 + (r["Stop"]/entry_price - 1.0)*100.0*0.55

    asof_close = df[df[date_col]==asof][close_col]
    if asof_close.empty:
        asof_close = df[df[date_col] < asof][close_col].iloc[-1:]
    bh_ret = (exit_close/asof_close.iloc[-1] - 1.0)*100.0

    # Escursioni su close nel periodo (proxy di MAE/MFE)
    period = after.iloc[:int(r["H_min"])+1]
    min_close = period[close_col].min()
    max_close = period[close_col].max()
    mae_close_pct = (min_close/entry_close - 1.0)*100.0
    mfe_close_pct = (max_close/entry_close - 1.0)*100.0

    # Vol regime: stdev 20g prima dell’ingresso
    prior = df[df[date_col] < entry_day].tail(21)
    if len(prior) >= 21:
        ret = prior[close_col].pct_change().dropna()
        vol20 = ret.std()*np.sqrt(252)
    else:
        vol20 = np.nan

    rows.append({**r.to_dict(),
                 "PnL_atteso_%":round(exp_ret,2),
                 "PnL_real_%":round(pnl_real,2),
                 "BH_ret_%":round(bh_ret,2),
                 "MAE_close_%":round(mae_close_pct,2),
                 "MFE_close_%":round(mfe_close_pct,2),
                 "vol20": round(vol20,3) if pd.notna(vol20) else np.nan,
                 "entry_day":str(entry_day.date()),
                 "exit_day":str(horizon_end.date())})

out = pd.DataFrame(rows)

# Merge asset class se disponibile
if 'Ticker' in out.columns and u is not None:
    out = out.merge(u, on="Ticker", how="left")

# Sensibilità (±1% su Entry/Stop/TP -> Expected P&L)
def exp_ret(entry, stop, tp):
    return (tp/entry - 1)*100*0.45 + (stop/entry - 1)*100*0.55
out["Exp_delta_-1%"] = exp_ret(out["Entry"]*0.99, out["Stop"]*0.99, out["TP"]*0.99)
out["Exp_delta_1%"]  = exp_ret(out["Entry"]*1.01, out["Stop"]*1.01, out["TP"]*1.01)

entered = out[~out["note"].fillna("").str.contains("non entrato")]
hit_rate  = float((entered["PnL_real_%"]>0).mean()) if len(entered)>0 else np.nan
expectancy= float(entered["PnL_real_%"].mean()) if len(entered)>0 else np.nan

# Vol buckets (terzili)
if entered["vol20"].notna().sum() >= 3:
    qs = entered["vol20"].quantile([0.33,0.66]).values
    def bucket(v):
        if pd.isna(v): return "NA"
        if v<=qs[0]: return "LOW"
        if v<=qs[1]: return "MID"
        return "HIGH"
    entered["vol_bucket"] = entered["vol20"].apply(bucket)

# Summary markdown
lines = []
lines += [f"# Retro report — as of {args.as_of}",
          "",
          f"- Slippage applicato: **{args.slippage_bps} bps** (peggiorativo su entry & exit)",
          f"- Trades totali: {len(out)} | Entrati: {len(entered)}",
          f"- Hit-rate: {hit_rate:.2%}" if not np.isnan(hit_rate) else "- Hit-rate: n/d",
          f"- Expectancy (media P&L reale): {expectancy:.2f}%" if not np.isnan(expectancy) else "- Expectancy: n/d",
          "",
          "## Top 5 segnali per P&L atteso",
          "",
          "| Ticker | Entry | Stop | TP | H_min | entry_day | exit_day | P&L atteso % | P&L reale % | B&H % | MAE% | MFE% |",
          "|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|"]
top5 = out.sort_values("PnL_atteso_%", ascending=False).head(5)
for _, r in top5.iterrows():
    lines.append(f"| {r['Ticker']} | {r['Entry']:.2f} | {r['Stop']:.2f} | {r['TP']:.2f} | {int(r['H_min'])} | {r['entry_day']} | {r['exit_day']} | {r['PnL_atteso_%']:.2f} | {r['PnL_real_%']:.2f} | {r['BH_ret_%']:.2f} | {r['MAE_close_%']:.2f} | {r['MFE_close_%']:.2f} |")

# Asset Class
if "AssetClass" in out.columns:
    lines += ["", "## Performance per Asset Class", "",
              "| AssetClass | N | P&L reale medio % | Hit-rate |",
              "|---|---:|---:|---:|"]
    g = entered.groupby("AssetClass")["PnL_real_%"]
    for k, srs in g:
        lines.append(f"| {k} | {len(srs)} | {srs.mean():.2f} | {(srs>0).mean():.2%} |")

# Vol regimes
if "vol_bucket" in entered.columns:
    lines += ["", "## Performance per regime di volatilità (20d)", "",
              "| Vol bucket | N | P&L reale medio % | Hit-rate |",
              "|---|---:|---:|---:|"]
    g = entered.groupby("vol_bucket")["PnL_real_%"]
    for k, srs in g:
        lines.append(f"| {k} | {len(srs)} | {srs.mean():.2f} | {(srs>0).mean():.2%} |")

# Sensibilità
lines += ["", "## Sensibilità expected P&L (±1%)", "",
          "| Scenario | Expected P&L medio % |",
          "|---|---:|",
          f"| Base | {out['PnL_atteso_%'].mean():.2f} |",
          f"| Entry/Stop/TP -1% | {out['Exp_delta_-1%'].mean():.2f} |",
          f"| Entry/Stop/TP +1% | {out['Exp_delta_1%'].mean():.2f} |"]

Path(args.outdir,"retro_signals_eval.csv").write_text(out.to_csv(index=False))
Path(args.outdir,"summary.md").write_text("\n".join(lines))
print("Wrote retro/summary.md and retro/retro_signals_eval.csv")
