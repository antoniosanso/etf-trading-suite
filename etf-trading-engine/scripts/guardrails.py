import argparse, json, yaml, sys, os, math, csv, glob

def read_kpis(path):
    try:
        with open(path,'r',encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def dd_from_equity(csv_path):
    try:
        with open(csv_path,'r',encoding='utf-8') as f:
            reader = csv.DictReader(f)
            eq = []
            cols = None
            for row in reader:
                if cols is None:
                    cols = [c for c in row.keys() if c.lower() in ("equity","nav","equitycurve","curve")]
                val = None
                for c in cols or []:
                    if row.get(c):
                        try:
                            val = float(row[c]); break
                        except: pass
                if val is not None: eq.append(val)
            if len(eq) < 3: return None
            peak = eq[0]; maxdd = 0.0
            for v in eq:
                peak = max(peak, v)
                if peak > 0:
                    dd = (peak - v) / peak
                    if dd > maxdd: maxdd = dd
            return float(maxdd)
    except Exception:
        return None

def auto_find_equity():
    cand = []
    for pat in ("outputs/*equity*.csv","outputs/*Equity*.csv","*equity*.csv"):
        cand += glob.glob(pat)
    return cand[0] if cand else None

def classify(kpis, cfg):
    sc = cfg.get('stop_criteria', {})
    min_sharpe = float(sc.get('min_sharpe', 0.30))
    pf_min = float(sc.get('profit_factor_min', 1.10))
    maxdd_limit = float(sc.get('maxdd_limit_pct', 0.35))
    wf_cov_max = float(sc.get('wf_calmar_var_max_pct', 30.0))

    sharpe = float(kpis.get('Sharpe', 0.0))
    pf = float(kpis.get('ProfitFactor', 0.0))
    maxdd = float(kpis.get('MaxDD_Pct', 1.0))
    calmar_cov = float((kpis.get('WF', {}) or {}).get('Calmar_CoV_pct', 0.0))

    yb_sharpe = max(0.0, min_sharpe - 0.05)
    yb_pf     = max(1.0, pf_min - 0.04)

    status, issues = "GREEN", []
    def degrade(to):
        nonlocal status
        if to == "RED": status = "RED"
        elif status != "RED": status = "YELLOW"

    if sharpe < min_sharpe:
        issues.append(f"Sharpe<{min_sharpe} (got {sharpe:.3f})")
        degrade("RED")
        if sharpe >= yb_sharpe and calmar_cov <= wf_cov_max:
            status = "YELLOW"
    if pf < pf_min:
        issues.append(f"ProfitFactor<{pf_min} (got {pf:.2f})")
        degrade("RED")
        if pf >= yb_pf and calmar_cov <= wf_cov_max and status != "RED":
            status = "YELLOW"
    if maxdd > maxdd_limit:
        issues.append(f"MaxDD>{maxdd_limit*100:.0f}% (got {maxdd*100:.0f}%)")
        degrade("RED")
    if calmar_cov > wf_cov_max:
        issues.append(f"WF Calmar CoV>{wf_cov_max}% (got {calmar_cov:.1f}%)")
        degrade("RED")

    return status, issues

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--kpis', required=True)
    ap.add_argument('--wf', required=False)
    ap.add_argument('--equity', required=False, help='equity_curve.csv for fallback MaxDD')
    ap.add_argument('--out', default='./outputs/guardrails_status.json')
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config,'r',encoding='utf-8'))
    k = read_kpis(a.kpis)

    eq_path = a.equity or auto_find_equity()
    if eq_path and (not isinstance(k.get('MaxDD_Pct', None), (int,float)) or float(k.get('MaxDD_Pct', 1.0)) >= 0.99):
        fallback_dd = dd_from_equity(eq_path)
        if fallback_dd is not None:
            k['_EquityDD_Fallback'] = fallback_dd
            k['MaxDD_Pct'] = float(fallback_dd)

    if a.wf and os.path.exists(a.wf):
        try: k['WF'] = json.load(open(a.wf,'r',encoding='utf-8'))
        except Exception: k['WF'] = {}

    st, issues = classify(k, cfg)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out,'w',encoding='utf-8') as f:
        json.dump({"status":st,"issues":issues,"kpis":k}, f, indent=2)
    print("GUARDRAILS:", st, "->", "; ".join(issues) if issues else "OK")
    sys.exit(0 if st=="GREEN" else (2 if st=="YELLOW" else 3))

if __name__ == '__main__':
    main()
