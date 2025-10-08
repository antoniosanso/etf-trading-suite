import argparse, json, yaml, sys

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
    min_sharpe = float(stop.get('min_sharpe', 0.20))
    maxdd_limit = float(stop.get('maxdd_limit_pct', 0.35))
    profit_factor_min = float(stop.get('profit_factor_min', 1.05))
    wf_calmar_var_max_pct = float(stop.get('wf_calmar_var_max_pct', 15.0))

    cond_sharpe = float(kpis.get('Sharpe', 0.0)) >= min_sharpe
    cond_pf = float(kpis.get('ProfitFactor', 0.0)) >= profit_factor_min
    cond_dd = abs(float(kpis.get('MaxDD', -1.0))) <= maxdd_limit

    calmar_cov_pct = float(wf.get('aggregates',{}).get('calmar_cov_pct', 999.0))
    cond_wf = calmar_cov_pct <= wf_calmar_var_max_pct

    reasons = []
    if not cond_sharpe: reasons.append(f"Sharpe<{min_sharpe}")
    if not cond_pf: reasons.append(f"ProfitFactor<{profit_factor_min}")
    if not cond_dd: reasons.append(f"|MaxDD|>{maxdd_limit*100:.0f}%")
    if not cond_wf: reasons.append(f"WF Calmar CoV>{wf_calmar_var_max_pct}%")

    if reasons:
        print("GUARDRAILS: FAIL -> " + ", ".join(reasons))
        sys.exit(3)
    else:
        print("GUARDRAILS: PASS")

if __name__ == "__main__":
    main()
