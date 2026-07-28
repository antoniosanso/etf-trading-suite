from src.engine.backtest import run_backtest, validate_prices
from src.engine.metrics import sharpe, max_drawdown, calmar, profit_factor
from src.engine.strategy import (
    breakout_entries, channel_rebound_entries, enrich,
    multi_horizon_breakout_entries, trend_pullback_entries,
    shock_reversion_entries, false_breakdown_reclaim_entries,
)
import pandas as pd
import numpy as np
import pytest

def test_metrics_smoke():
    r = pd.Series([0.0, 0.01, -0.005, 0.002])
    eq = (1+r).cumprod()*100
    assert -1.0 <= max_drawdown(eq) <= 0.0
    assert profit_factor(r) > 0.0
    _ = sharpe(r); _ = calmar(r, eq)


def prices(rows=320, start=100.0):
    dates = pd.bdate_range("2024-01-01", periods=rows)
    close = start + np.arange(rows) * 0.10
    return pd.DataFrame({
        "Date": dates, "Ticker": "TEST.MI", "Open": close,
        "High": close + 0.02, "Low": close - 0.02, "Close": close,
        "Volume": 100_000,
    })


def config(active="S1_breakout"):
    return {
        "active_run": active,
        "general": {
            "capital_eur": 10_000,
            "data": {"strict_quality": True},
            "risk": {"default_risk_per_trade_pct": 1.0},
            "execution": {},
        },
        "runs": {
            "S1_breakout": {
                "entry": {"lookback_days": 20, "buffer_pct": 0},
                "stop_loss": {"mode": "percent", "value_pct": 7},
                "take_profit": {"mode": "percent", "value_pct": 14},
            },
            "S2_multilayer": {
                "capital_weights": {"core_pct": 70, "tactical_pct": 30},
                "core": {
                    "scaling_tranches": [
                        {"mode": "market_now", "weight_pct": 33},
                        {"mode": "pullback_dma", "weight_pct": 33},
                        {"mode": "multi_horizon_breakout", "weight_pct": 34,
                         "lookback_days": [20, 40, 60],
                         "min_confirmations": 2},
                    ],
                    "trailing_pct_by_ticker": {"default": 12},
                },
                "tactical": {
                    "entry": {"lookback_days": 20, "buffer_pct": 0},
                    "stop_loss": {"mode": "percent", "value_pct": 7},
                    "take_profit": {"mode": "percent", "value_pct": 14},
                },
            },
            "S4_channel_rebound": {
                "entry": {"lookback_days": 30, "min_channel_score": 0.2,
                          "lower_band_tolerance_atr": 0.5},
                "stop_loss": {"mode": "below_channel_atr", "atr_multiplier": 0.6},
                "take_profit": {"tp1": "channel_midline", "tp2": "channel_upper_band"},
                "risk": {"risk_per_trade_pct": 0.5},
            },
            "S5_trend_pullback": {
                "entry": {"mode": "trend_pullback", "tolerance_atr": 0.5,
                          "rsi_min": 20, "rsi_max": 70},
                "stop_loss": {"mode": "signal_low_atr", "atr_multiplier": 0.5},
                "take_profit": {"mode": "percent", "value_pct": 10},
            },
            "S6_multi_horizon_breakout": {
                "entry": {"mode": "multi_horizon_breakout",
                          "lookback_days": [20, 40, 60],
                          "min_confirmations": 2, "buffer_pct": 0,
                          "trend_filter": False},
                "stop_loss": {"mode": "percent", "value_pct": 7},
                "take_profit": {"mode": "percent", "value_pct": 14},
            },
            "S7_shock_reversion": {
                "entry": {"mode": "shock_reversion", "shock_window_days": 5,
                          "shock_atr_multiple": 2.0, "close_z_max": -1.0,
                          "rsi_max": 40,
                          "confirmation": "close_above_reversal_high"},
                "stop_loss": {"mode": "signal_low_atr", "atr_multiplier": 0.5},
                "take_profit": {"mode": "moving_average", "field": "EMA20",
                                "fallback_atr_multiple": 1.5},
            },
            "S8_false_breakdown_reclaim": {
                "entry": {"mode": "false_breakdown_reclaim",
                          "support_lookback_days": 20,
                          "support_min_periods": 10,
                          "support_quantile": 0.10,
                          "min_support_touches": 1,
                          "touch_tolerance_atr": 1.0,
                          "break_buffer_atr": 0.05,
                          "reclaim_buffer_atr": 0.0,
                          "max_reclaim_days": 2,
                          "min_close_location": 0.55},
                "stop_loss": {"mode": "breakdown_low_atr", "atr_multiplier": 0.25},
                "take_profit": {"mode": "moving_average", "field": "EMA20",
                                "fallback_atr_multiple": 2.0},
            },
        },
    }


def test_quality_gate_rejects_impossible_ohlc():
    df = prices()
    df.loc[0, "Low"] = df.loc[0, "High"] + 1
    with pytest.raises(ValueError, match="quality gate"):
        validate_prices(df, strict=True)


def test_breakout_uses_previous_high_without_lookahead():
    df = enrich(prices(30))
    signal = breakout_entries(df, lookback=20, buffer_pct=0)
    assert not signal.iloc[:20].any()
    assert signal.iloc[20:].any()


def test_event_backtest_returns_trade_ledger_and_kpis():
    out = run_backtest(prices(), config())
    assert out["active_run"] == "S1_breakout"
    assert set(("kpis", "trades", "equity_curve", "data_quality")) <= set(out)
    assert out["kpis"]["Trades"] >= 1
    assert all(t["quantity"] == int(t["quantity"]) for t in out["trades"])


def test_channel_strategy_does_not_buy_unconfirmed_fall():
    df = prices(100)
    df["Close"] = np.linspace(100, 70, len(df))
    df["Open"] = df["Close"] + 0.1
    df["High"] = df[["Open", "Close"]].max(axis=1) + 0.2
    df["Low"] = df[["Open", "Close"]].min(axis=1) - 0.2
    signal = channel_rebound_entries(enrich(df), {
        "lookback_days": 30, "lower_band_tolerance_atr": 0.5,
        "min_channel_score": 0.1,
    })
    assert not signal.any()


def test_multi_horizon_breakout_requires_configured_consensus():
    df = enrich(prices(100))
    signal = multi_horizon_breakout_entries(df, {
        "lookback_days": [20, 40, 60], "min_confirmations": 2,
        "buffer_pct": 0, "trend_filter": False,
    })
    assert not signal.iloc[:40].any()
    assert signal.iloc[60:].any()


def test_pullback_requires_next_bar_confirmation():
    df = prices(260)
    close = np.linspace(100, 140, len(df))
    close[-3:] = [136.0, 135.0, 138.0]
    df["Close"] = close
    df["Open"] = close - 0.1
    df["High"] = np.maximum(df["Open"], df["Close"]) + 0.2
    df["Low"] = np.minimum(df["Open"], df["Close"]) - 0.2
    out = enrich(df)
    signal = trend_pullback_entries(out, {
        "tolerance_atr": 1.0, "rsi_min": 0, "rsi_max": 100,
        "sma50_slope_min": 0,
    })
    assert not signal.iloc[-2]
    assert signal.iloc[-1]


def test_shock_reversion_does_not_fire_on_shock_bar():
    df = prices(80)
    close = np.linspace(100, 110, len(df))
    close[-2] = 95
    close[-1] = 98
    df["Close"] = close
    df["Open"] = close - 0.2
    df["High"] = np.maximum(df["Open"], df["Close"]) + 0.3
    df["Low"] = np.minimum(df["Open"], df["Close"]) - 0.3
    out = enrich(df)
    signal = shock_reversion_entries(out, {
        "shock_window_days": 5, "shock_atr_multiple": 1.0,
        "close_z_max": -1.0, "rsi_max": 60,
        "confirmation": "close_above_reversal_high",
    })
    assert not signal.iloc[-2]
    assert signal.iloc[-1]


def test_false_breakdown_uses_prior_support_and_requires_reclaim():
    df = prices(50)
    close = np.full(len(df), 100.0)
    close[-2:] = [97.5, 100.2]
    df["Close"] = close
    df["Open"] = close
    df["High"] = close + 0.5
    df["Low"] = close - 0.5
    df.loc[df.index[-2], ["Open", "High", "Low", "Close"]] = [100.0, 100.2, 96.5, 97.5]
    # Reclaims the old frozen level but does not create a fresh breakdown.
    df.loc[df.index[-1], ["Open", "High", "Low", "Close"]] = [99.7, 100.5, 99.6, 100.2]
    out = enrich(df)
    signal = false_breakdown_reclaim_entries(out, {
        "support_lookback_days": 20, "support_min_periods": 10,
        "support_quantile": 0.10, "min_support_touches": 1,
        "touch_tolerance_atr": 1.0, "break_buffer_atr": 0.05,
        "max_reclaim_days": 2, "min_close_location": 0.55,
    })
    assert not signal.iloc[-2]
    assert signal.iloc[-1]
    assert out["FalseBreakdownLow"].iloc[-1] == pytest.approx(96.5)


def test_false_breakdown_does_not_reclaim_after_expiry():
    df = prices(55)
    df[["Open", "High", "Low", "Close"]] = [100.0, 100.5, 99.5, 100.0]
    df.loc[df.index[-4], ["Open", "High", "Low", "Close"]] = [100.0, 100.2, 96.5, 97.0]
    df.loc[df.index[-1], ["Open", "High", "Low", "Close"]] = [98.0, 100.5, 97.8, 100.2]
    signal = false_breakdown_reclaim_entries(enrich(df), {
        "support_lookback_days": 20, "support_min_periods": 10,
        "support_quantile": 0.10, "min_support_touches": 1,
        "touch_tolerance_atr": 1.0, "break_buffer_atr": 0.05,
        "max_reclaim_days": 2, "min_close_location": 0.55,
    })
    assert not signal.iloc[-1]


@pytest.mark.parametrize("active", [
    "S5_trend_pullback", "S6_multi_horizon_breakout", "S7_shock_reversion",
    "S8_false_breakdown_reclaim",
])
def test_new_strategies_execute(active):
    out = run_backtest(prices(), config(active))
    assert out["active_run"] == active
    assert set(("kpis", "trades", "orders")) <= set(out)


def test_multilayer_runs_three_independent_core_tranches():
    out = run_backtest(prices(), config("S2_multilayer"))
    assert out["active_run"] == "S2_multilayer"
    assert len(out["layers"]["core_tranches"]) == 3
    assert "tactical" in out["layers"]


def test_evaluation_history_is_warmup_not_trading_period():
    cfg = config("S1_breakout")
    cfg["general"]["evaluation"] = {
        "start": "2025-01-01", "end": "2025-03-31"
    }
    out = run_backtest(prices(), cfg)
    assert all(t["entry_date"] >= "2025-01-01" for t in out["trades"])
