import pandas as pd
import pytest

from src.engine.operations import build_orders
from src.engine.trading_costs import FinecoCosts, position_size


def test_costs_include_spread_commission_and_tax():
    costs = FinecoCosts(commission_eur=10, spread_bps=20, tax_rate=.26)
    result = costs.round_trip_cost(10, 100, 110)
    assert result["buy_price"] == 100.1
    assert result["sell_price"] == 109.89
    assert result["tax"] > 0
    assert result["net_pnl"] < result["gross_pnl"]


def test_position_size_respects_cash_and_risk():
    costs = FinecoCosts(commission_eur=0, spread_bps=0)
    assert position_size(10_000, 1, 100, 95, costs) == 20
    assert position_size(10_000, 1, 100, 100, costs) == 0


def test_operational_orders_have_required_levels():
    signals = pd.DataFrame([{
        "Ticker": "ETF.MI", "Entry": 100, "Stop": 94.5, "TP1": 111.25,
        "Reason": "breakout",
    }])
    orders = build_orders(signals, 10_000, costs=FinecoCosts(0, 0))
    assert orders.loc[0, "Stop"] == 94.5
    assert round(orders.loc[0, "Target"], 8) == 111.25
    assert orders.loc[0, "Quantity"] > 0
    assert "stop" in orders.loc[0, "Exit"]


def test_operational_orders_reject_fixed_percentage_fallbacks():
    signals = pd.DataFrame([{"Ticker": "ETF.MI", "Entry": 100}])
    with pytest.raises(ValueError, match="strategy-calculated"):
        build_orders(signals, 10_000, costs=FinecoCosts(0, 0))
