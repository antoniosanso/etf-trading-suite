from datetime import datetime, timezone
import json

import pandas as pd

from src.engine.operations import build_orders
from src.engine.safety import data_is_fresh, load_economic_validation
from scripts.economic_gate import evaluate


def signal(strategy="S3_breakout_checklist"):
    return pd.DataFrame([{
        "Ticker": "ETF.MI", "Entry": 100, "Stop": 95, "TP1": 110,
        "Run": strategy, "Reason": "test",
    }])


def test_missing_or_failed_validation_blocks(tmp_path):
    assert load_economic_validation(tmp_path / "missing.json")["status"] == "BLOCKED"
    path = tmp_path / "gate.json"
    path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED", "approved_strategies": [],
    }))
    assert load_economic_validation(path)["status"] == "BLOCKED"


def test_orders_are_proposals_and_require_manual_confirmation():
    orders = build_orders(signal(), 105_000, approved_strategies={"S3_breakout_checklist"})
    assert orders.loc[0, "Status"] == "PROPOSAL_ONLY"
    assert bool(orders.loc[0, "RequiresManualConfirmation"])
    assert orders.loc[0, "OrderType"] == "LIMIT"
    assert orders.loc[0, "PositionValue"] <= 52_500


def test_unapproved_strategy_produces_zero_orders():
    orders = build_orders(signal("S5_trend_pullback"), 105_000,
                          approved_strategies={"S3_breakout_checklist"})
    assert orders.empty


def test_aggregate_risk_is_capped():
    signals = pd.concat([signal().assign(Ticker=f"ETF{i}.MI") for i in range(5)])
    orders = build_orders(signals, 105_000, risk_pct=2,
                          max_positions=5, max_total_risk_pct=3,
                          approved_strategies={"S3_breakout_checklist"})
    assert orders["RiskEUR"].sum() <= 3_150


def test_stale_market_data_blocks():
    old = pd.DataFrame({"Date": ["2020-01-01"]})
    ok, reason = data_is_fresh(old, now=datetime(2026, 7, 28, tzinfo=timezone.utc))
    assert not ok
    assert "stale" in reason


def test_economic_gate_requires_all_thresholds():
    report = {
        "windows": [
            {"strategy": "S3", "CAGR": .1} for _ in range(4)
        ] + [{"strategy": "S3", "CAGR": -.1}],
        "aggregates": {"S3": {
            "windows_count": 5, "sharpe_mean": .4,
            "profit_factor_mean": 1.2, "maxdd_mean": -.2,
            "trades_total": 10,
        }},
    }
    assert evaluate(report, 5, .3, 1.1, .3)["status"] == "PASS"
    report["aggregates"]["S3"]["profit_factor_mean"] = .9
    assert evaluate(report, 5, .3, 1.1, .3)["status"] == "BLOCKED"
