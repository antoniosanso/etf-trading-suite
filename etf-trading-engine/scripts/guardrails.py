import argparse, json, yaml, sys, numpy as np, math

def trimmed_cov(calmar_list, trim=1):
    x = [float(v) for v in calmar_list if v is not None and math.isfinite(float(v))]
    if not x:
        return float('nan')
    arr = np.array(sorted(x), dtype=float)
    if trim>0 and arr.size > 2*trim:
        arr = arr[trim:-trim]
    m = float(np.nanmean(arr)); s = float(np.nanstd(arr))
    return (s / (abs(m)+1e-12)) * 100.0

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
    min_sharpe = float(stop.get('min_sharpe', 0.25))         # temporary relaxed
    maxdd_limit = float(stop.get('maxdd_limit_pct', 0.35))
    profit_factor_min = float(stop.get('profit_factor_min', 1.05)) # temporary relaxed
    wf_calmar_var_max_pct = float(stop.get('wf_calmar_var_max_pct', 40.0)) # temporary relaxed
    wf_trim = int(stop.get('wf_trim', 1))

    cond_sharpe = float(kpis.get('Sharpe', 0.0)) >= min_sharpe
    cond_pf = float(kpis.get('ProfitFactor', 0.0)) >= profit_factor_min
    cond_dd = abs(float(kpis.get('MaxDD', -1.0))) <= maxdd_limit

    wins = wf.get('windows', [])
    calmar_vals = [w.get('Calmar') for w in wins if 'Calmar' in w]
    cov = trimmed_cov(calmar_vals, wf_trim) if calmar_vals else float('nan')
    cond_wf = not math.isnan(cov) and (cov <= wf_calmar_var_max_pct)

    reasons = []
    if not cond_sharpe: reasons.append(f"Sharpe<{min_sharpe}")
    if not cond_pf: reasons.append(f"ProfitFactor<{profit_factor_min}")
    if not cond_dd: reasons.append(f"|MaxDD|>{maxdd_limit*100:.0f}%")
    if math.isnan(cov): reasons.append("WF incomplete (Calmar NaN)")
    elif not cond_wf: reasons.append(f"WF Calmar CoV>{wf_calmar_var_max_pct}% (trim={wf_trim}, got={cov:.2f}%)")

    if reasons:
        print("GUARDRAILS: FAIL -> " + ", ".join(reasons))
        sys.exit(3)
    else:
        print("GUARDRAILS: PASS")

if __name__ == "__main__":
    main()
