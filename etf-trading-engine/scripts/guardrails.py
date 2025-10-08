import argparse, json, yaml, sys, numpy as np, math, os
from pathlib import Path

def trimmed_cov(calmar_list, trim=1):
    vals = [float(v) for v in calmar_list if v is not None and math.isfinite(float(v))]
    if not vals:
        return float('nan')
    arr = np.array(sorted(vals), dtype=float)
    if trim>0 and arr.size > 2*trim:
        arr = arr[trim:-trim]
    m = float(np.nanmean(arr)); s = float(np.nanstd(arr))
    return (s / (abs(m)+1e-12)) * 100.0

def borderline_ge(value, thresh, tol=0.10):
    # borderline if within 10% below threshold
    return (value < thresh) and (value >= (1.0 - tol) * thresh)

def borderline_le(value, thresh, tol=0.10):
    # borderline if within 10% above threshold (for max constraints)
    return (value > thresh) and (value <= (1.0 + tol) * thresh)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--kpis', required=True)
    ap.add_argument('--wf', required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config,'r',encoding='utf-8'))
    kpis = json.load(open(args.kpis,'r',encoding='utf-8'))
    wf = json.load(open(args.wf,'r',encoding='utf-8'))

    stop = cfg.get('stop_criteria', {})
    min_sharpe = float(stop.get('min_sharpe', 0.30))
    pf_min = float(stop.get('profit_factor_min', 1.10))
    dd_max = float(stop.get('maxdd_limit_pct', 0.35))
    cov_max = float(stop.get('wf_calmar_var_max_pct', 0.30))
    wf_trim = int(stop.get('wf_trim', 1))

    sharpe = float(kpis.get('Sharpe', float('nan')))
    pf = float(kpis.get('ProfitFactor', float('nan')))
    maxdd = abs(float(kpis.get('MaxDD', float('nan'))))

    wins = wf.get('windows', [])
    calmar_vals = [w.get('Calmar') for w in wins if 'Calmar' in w]
    cov = trimmed_cov(calmar_vals, wf_trim) if calmar_vals else float('nan')

    reasons_red = []
    reasons_yellow = []

    # PASS/RED/YELLOW logic
    # Sharpe and PF are strict (no relaxation). Borderline = within 10% of threshold.
    if math.isnan(sharpe): reasons_yellow.append("Sharpe:NaN")
    elif sharpe < min_sharpe:
        if borderline_ge(sharpe, min_sharpe): reasons_yellow.append(f"Sharpe borderline ({sharpe:.3f} < {min_sharpe})")
        else: reasons_red.append(f"Sharpe<{min_sharpe} (got {sharpe:.3f})")

    if math.isnan(pf): reasons_yellow.append("ProfitFactor:NaN")
    elif pf < pf_min:
        if borderline_ge(pf, pf_min): reasons_yellow.append(f"ProfitFactor borderline ({pf:.2f} < {pf_min})")
        else: reasons_red.append(f"ProfitFactor<{pf_min} (got {pf:.2f})")

    if math.isnan(maxdd): reasons_yellow.append("MaxDD:NaN")
    elif maxdd > dd_max:
        if borderline_le(maxdd, dd_max): reasons_yellow.append(f"|MaxDD| borderline ({maxdd:.3f} > {dd_max})")
        else: reasons_red.append(f"|MaxDD|>{dd_max*100:.0f}% (got {maxdd*100:.1f}%)")

    if math.isnan(cov):
        reasons_yellow.append("WF incomplete (Calmar NaN)")
    elif cov > cov_max:
        if borderline_le(cov, cov_max): reasons_yellow.append(f"WF Calmar CoV borderline ({cov:.2f}% > {cov_max:.2f}%)")
        else: reasons_red.append(f"WF Calmar CoV>{cov_max:.2f}% (got {cov:.2f}%)")

    status = "PASS" if not reasons_red and not reasons_yellow else ("YELLOW" if not reasons_red else "RED")
    msg = f"GUARDRAILS: {status}"
    if reasons_red or reasons_yellow:
        reasons = reasons_red + reasons_yellow
        msg += " -> " + ", ".join(reasons)
    print(msg)

    # persist status for reports
    outdir = Path("./outputs"); outdir.mkdir(exist_ok=True, parents=True)
    payload = {
        "status": status,
        "reasons_red": reasons_red,
        "reasons_yellow": reasons_yellow,
        "values": {
            "Sharpe": sharpe, "ProfitFactor": pf, "MaxDD_abs": maxdd, "WF_Calmar_CoV_pct": cov
        },
        "thresholds": {
            "Sharpe_min": min_sharpe, "ProfitFactor_min": pf_min, "MaxDD_max": dd_max, "WF_Calmar_CoV_max": cov_max, "WF_trim": wf_trim
        }
    }
    (outdir / "guardrails_status.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # exit code: RED -> 3, else 0 (PASS/YELLOW)
    sys.exit(3 if status == "RED" else 0)

if __name__ == "__main__":
    main()
