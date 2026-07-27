"""Italian retail trading costs and position sizing utilities."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class FinecoCosts:
    """Configurable approximation of a Fineco execution profile.

    Fees vary by customer profile and market, therefore every value is exposed
    in the UI/configuration rather than presented as an authoritative tariff.
    """

    commission_eur: float = 19.0
    spread_bps: float = 10.0
    tax_rate: float = 0.26

    def execution_price(self, mid_price: float, side: str) -> float:
        half_spread = self.spread_bps / 20_000
        return mid_price * (1 + half_spread if side.upper() == "BUY" else 1 - half_spread)

    def round_trip_cost(self, quantity: int, entry: float, exit_price: float) -> dict:
        buy = self.execution_price(entry, "BUY")
        sell = self.execution_price(exit_price, "SELL")
        gross = quantity * (sell - buy)
        commissions = 2 * self.commission_eur
        taxable_profit = max(0.0, gross - commissions)
        tax = taxable_profit * self.tax_rate
        return {
            "gross_pnl": gross,
            "commissions": commissions,
            "tax": tax,
            "net_pnl": gross - commissions - tax,
            "buy_price": buy,
            "sell_price": sell,
        }


def position_size(capital: float, risk_pct: float, entry: float, stop: float,
                  costs: FinecoCosts, max_allocation_pct: float = 100.0) -> int:
    """Return whole units bounded by risk budget and available allocation."""
    if capital <= 0 or entry <= 0 or stop >= entry or risk_pct <= 0:
        return 0
    buy = costs.execution_price(entry, "BUY")
    risk_per_unit = buy - costs.execution_price(stop, "SELL")
    risk_budget = capital * risk_pct / 100 - 2 * costs.commission_eur
    allocation = capital * max_allocation_pct / 100
    by_risk = math.floor(max(0.0, risk_budget) / risk_per_unit)
    by_cash = math.floor(max(0.0, allocation - costs.commission_eur) / buy)
    return max(0, min(by_risk, by_cash))
