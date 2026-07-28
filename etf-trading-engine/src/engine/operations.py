"""Generate executable, auditable trading proposals from ranked signals."""

import pandas as pd

from .trading_costs import FinecoCosts, position_size


def build_orders(signals: pd.DataFrame, capital: float, risk_pct: float = 1.0,
                 costs: FinecoCosts | None = None, max_positions: int = 3,
                 max_allocation_pct: float = 50.0,
                 max_total_risk_pct: float = 3.0,
                 approved_strategies: set[str] | None = None,
                 proposal_only: bool = True) -> pd.DataFrame:
    costs = costs or FinecoCosts()
    columns = ["Status", "RequiresManualConfirmation", "Ticker", "Action",
               "OrderType", "LimitPrice", "Entry", "Exit", "Stop", "Target",
               "Quantity", "PositionValue", "RiskEUR", "CommissionRT",
               "TaxRate", "Strategy", "Reason"]
    if signals.empty or "Ticker" not in signals:
        return pd.DataFrame(columns=columns)
    price_col = next((c for c in ("Entry", "Close", "Price") if c in signals), None)
    if not price_col:
        return pd.DataFrame(columns=columns)
    if "Stop" not in signals or not ({"TP1", "Target"} & set(signals.columns)):
        raise ValueError(
            "Each operation must include strategy-calculated Stop and TP1/Target levels"
        )
    rows = []
    total_risk = 0.0
    risk_cap = capital * max_total_risk_pct / 100
    for _, signal in signals.head(max_positions).iterrows():
        strategy = str(signal.get("Run", signal.get("Strategy", "")))
        if approved_strategies is not None and strategy not in approved_strategies:
            continue
        entry = float(signal[price_col])
        stop = float(signal["Stop"])
        target = float(signal["TP1"] if "TP1" in signal else signal["Target"])
        if not (stop < entry < target):
            raise ValueError(
                f"Invalid calculated levels for {signal['Ticker']}: require Stop < Entry < Target"
            )
        qty = position_size(capital, risk_pct, entry, stop, costs, max_allocation_pct)
        risk_eur = qty * (entry - stop) + 2 * costs.commission_eur
        if qty <= 0 or total_risk + risk_eur > risk_cap:
            continue
        total_risk += risk_eur
        rows.append({
            "Status": "PROPOSAL_ONLY" if proposal_only else "APPROVED",
            "RequiresManualConfirmation": True,
            "Ticker": signal["Ticker"], "Action": "BUY", "OrderType": "LIMIT",
            "LimitPrice": entry, "Entry": entry,
            "Exit": f"Target {target:.2f} o stop {stop:.2f}", "Stop": stop,
            "Target": target, "Quantity": qty, "PositionValue": qty * entry,
            "RiskEUR": risk_eur,
            "CommissionRT": 2 * costs.commission_eur, "TaxRate": costs.tax_rate,
            "Strategy": strategy,
            "Reason": signal.get("Reason", "Segnale quantitativo"),
        })
    return pd.DataFrame(rows, columns=columns)
