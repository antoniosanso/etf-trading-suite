"""Generate executable, auditable trading proposals from ranked signals."""

import pandas as pd

from .trading_costs import FinecoCosts, position_size


def build_orders(signals: pd.DataFrame, capital: float, risk_pct: float = 1.5,
                 stop_pct: float = 7.0, take_profit_pct: float = 14.0,
                 costs: FinecoCosts | None = None, max_positions: int = 3) -> pd.DataFrame:
    costs = costs or FinecoCosts()
    columns = ["Ticker", "Action", "Entry", "Exit", "Stop", "Target", "Quantity",
               "PositionValue", "RiskEUR", "CommissionRT", "TaxRate", "Reason"]
    if signals.empty or "Ticker" not in signals:
        return pd.DataFrame(columns=columns)
    price_col = next((c for c in ("Entry", "Close", "Price") if c in signals), None)
    if not price_col:
        return pd.DataFrame(columns=columns)
    rows = []
    allocation_pct = 100 / max(1, max_positions)
    for _, signal in signals.head(max_positions).iterrows():
        entry = float(signal[price_col])
        stop = float(signal.get("Stop", entry * (1 - stop_pct / 100)))
        target = float(signal.get("TP1", signal.get("Target", entry * (1 + take_profit_pct / 100))))
        qty = position_size(capital, risk_pct, entry, stop, costs, allocation_pct)
        rows.append({
            "Ticker": signal["Ticker"], "Action": "BUY", "Entry": entry,
            "Exit": f"Target {target:.2f} o stop {stop:.2f}", "Stop": stop,
            "Target": target, "Quantity": qty, "PositionValue": qty * entry,
            "RiskEUR": qty * (entry - stop) + 2 * costs.commission_eur,
            "CommissionRT": 2 * costs.commission_eur, "TaxRate": costs.tax_rate,
            "Reason": signal.get("Reason", "Segnale quantitativo"),
        })
    return pd.DataFrame(rows, columns=columns)
