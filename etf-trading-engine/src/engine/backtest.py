"""Event-driven, configuration-driven ETF backtester."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math

import numpy as np
import pandas as pd

from .metrics import sharpe, max_drawdown, calmar, profit_factor
from .strategy import (
    enrich, breakout_entries, channel_rebound_entries,
    multi_horizon_breakout_entries, trend_pullback_entries,
    shock_reversion_entries, false_breakdown_reclaim_entries,
)


REQUIRED = {"Date", "Ticker", "Open", "High", "Low", "Close", "Volume"}


def normalize_prices(prices: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "date": "Date", "dt": "Date", "ticker": "Ticker",
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    }
    rename = {col: aliases[col.strip().lower()]
              for col in prices.columns if col.strip().lower() in aliases}
    return prices.rename(columns=rename).copy()


def validate_prices(prices: pd.DataFrame, strict: bool = True) -> dict:
    prices = normalize_prices(prices)
    missing = sorted(REQUIRED - set(prices.columns))
    if missing:
        raise ValueError(f"Missing price columns: {', '.join(missing)}")
    numeric = ["Open", "High", "Low", "Close", "Volume"]
    bad_numeric = int(prices[numeric].isna().any(axis=1).sum())
    duplicate = int(prices.duplicated(["Ticker", "Date"]).sum())
    non_positive = int((prices[["Open", "High", "Low", "Close"]] <= 0).any(axis=1).sum())
    inconsistent = int((
        (prices["Low"] > prices[["Open", "Close", "High"]].min(axis=1)) |
        (prices["High"] < prices[["Open", "Close", "Low"]].max(axis=1))
    ).sum())
    report = {
        "rows": int(len(prices)), "duplicates": duplicate,
        "missing_numeric": bad_numeric, "non_positive_prices": non_positive,
        "inconsistent_ohlc": inconsistent,
    }
    if strict and any((duplicate, bad_numeric, non_positive, inconsistent)):
        raise ValueError(f"Price quality gate failed: {report}")
    return report


@dataclass
class Trade:
    ticker: str
    strategy: str
    entry_date: str
    entry: float
    exit_date: str
    exit: float
    quantity: int
    reason: str
    pnl: float
    return_pct: float
    ambiguous_bar: bool = False


def _costs(general: dict) -> dict:
    execution = general.get("execution", {})
    return {
        "commission_fixed": float(execution.get("commission_fixed_eur", 0.0)),
        "commission_pct": float(execution.get("commission_pct", 0.0)) / 100,
        "spread": float(execution.get("spread_pct", 0.0)) / 200,
        "slippage": float(execution.get("slippage_pct", 0.0)) / 100,
        "tax": float(execution.get("tax_rate_pct", 0.0)) / 100,
    }


def _fill(price: float, side: str, costs: dict) -> float:
    drag = costs["spread"] + costs["slippage"]
    return price * (1 + drag if side == "buy" else 1 - drag)


def _commission(notional: float, costs: dict) -> float:
    return costs["commission_fixed"] + abs(notional) * costs["commission_pct"]


def _adaptive_levels(df: pd.DataFrame, signal_index: int, entry: float,
                     cfg: dict) -> tuple[float, float]:
    """Calculate volatility- and structure-aware levels for one operation."""
    stop_cfg = cfg.get("stop_loss", {})
    tp_cfg = cfg.get("take_profit", {})
    lookback = int(stop_cfg.get("lookback_days", 20))
    atr_value = float(df.loc[signal_index, "ATR14"])
    recent_low = float(
        df.loc[max(0, signal_index - lookback + 1):signal_index, "Low"].min()
    )
    atr_stop = entry - float(stop_cfg.get("atr_multiple", 2.5)) * atr_value
    structural_stop = recent_low - float(
        stop_cfg.get("structure_buffer_atr", 0.25)
    ) * atr_value
    # Use the nearer valid protection while requiring room for normal volatility.
    stop = max(atr_stop, structural_stop)
    if not math.isfinite(stop) or stop >= entry:
        stop = atr_stop
    risk = entry - stop
    target = entry + max(
        float(tp_cfg.get("risk_multiple", 2.0)) * risk,
        float(tp_cfg.get("min_atr_multiple", 3.0)) * atr_value,
    )
    return stop, target


def _strategy_signals(df: pd.DataFrame, name: str, cfg: dict) -> pd.Series:
    if name == "S0_buyhold":
        signal = pd.Series(False, index=df.index)
        if len(signal):
            signal.iloc[0] = True
        return signal
    if name in {"S1_breakout", "S3_breakout_checklist"}:
        entry = cfg.get("entry", {})
        lookback = int(entry.get("lookback_days", 252))
        signal = breakout_entries(
            df, lookback, float(entry.get("buffer_pct", 0.3)),
            entry.get("volume_z_min"),
        )
        if name == "S3_breakout_checklist":
            required = {
                "S3TrendOK", "S3RegimeOK", "S3BreadthOK", "S3LiquidityOK",
            }
            missing = required - set(df.columns)
            if missing:
                raise ValueError(
                    "S3 market context missing: " + ", ".join(sorted(missing))
                )
            signal &= df[list(sorted(required))].all(axis=1)
        return signal.fillna(False)
    if name == "S4_channel_rebound":
        return channel_rebound_entries(df, cfg.get("entry", {}))
    if name in {"S5_trend_pullback", "S2_core_pullback"}:
        return trend_pullback_entries(df, cfg.get("entry", {}))
    if name in {"S6_multi_horizon_breakout", "S2_core_breakout"}:
        return multi_horizon_breakout_entries(df, cfg.get("entry", {}))
    if name == "S7_shock_reversion":
        return shock_reversion_entries(df, cfg.get("entry", {}))
    if name == "S8_false_breakdown_reclaim":
        return false_breakdown_reclaim_entries(df, cfg.get("entry", {}))
    raise ValueError(f"Unsupported run: {name}")


def _simulate_ticker(df: pd.DataFrame, ticker: str, name: str, cfg: dict,
                     general: dict, initial_cash: float) -> tuple[pd.Series, list[Trade]]:
    df = enrich(df.reset_index(drop=True))
    signals = _strategy_signals(df, name, cfg)
    evaluation = general.get("evaluation", {})
    trading_start = pd.Timestamp(evaluation["start"]) if evaluation.get("start") else None
    if name == "S0_buyhold" and trading_start is not None:
        signals[:] = False
        eligible = df.index[pd.to_datetime(df["Date"]) >= trading_start]
        if len(eligible):
            first = int(eligible[0])
            # Signals execute on the following open; place it on the prior row.
            signals.iloc[max(0, first - 1)] = True
    costs = _costs(general)
    risk_pct = float(cfg.get("risk", {}).get(
        "risk_per_trade_pct",
        general.get("risk", {}).get("default_risk_per_trade_pct", 1.0)
    )) / 100
    stop_cfg = cfg.get("stop_loss")
    tp_cfg = cfg.get("take_profit")
    trail_cfg = cfg.get("exit", {}).get("trailing_pct_by_ticker", {})
    cash, qty, entry, stop, tp = initial_cash, 0, 0.0, math.nan, math.nan
    entry_date, entry_cost = None, 0.0
    equity, trades = [], []

    for i, row in df.iterrows():
        entry_allowed = trading_start is None or pd.Timestamp(row.Date) >= trading_start
        if qty == 0 and i > 0 and entry_allowed and bool(signals.iloc[i - 1]):
            entry = _fill(float(row.Open), "buy", costs)
            if stop_cfg and stop_cfg.get("mode") == "percent":
                stop = entry * (1 - float(stop_cfg["value_pct"]) / 100)
            elif stop_cfg and stop_cfg.get("mode") == "adaptive_atr_structure":
                stop, _ = _adaptive_levels(df, i - 1, entry, cfg)
            elif name == "S4_channel_rebound":
                mult = float(stop_cfg.get("atr_multiplier", 0.6))
                stop = min(float(df.loc[i - 1, "Low"]),
                           float(df.loc[i - 1, "ChannelLower"])) - mult * float(df.loc[i - 1, "ATR14"])
            elif stop_cfg and stop_cfg.get("mode") == "signal_low_atr":
                stop = float(df.loc[i - 1, "Low"]) - \
                    float(stop_cfg.get("atr_multiplier", 0.5)) * float(df.loc[i - 1, "ATR14"])
            elif stop_cfg and stop_cfg.get("mode") == "breakdown_low_atr":
                stop = float(df.loc[i - 1, "FalseBreakdownLow"]) - \
                    float(stop_cfg.get("atr_multiplier", 0.25)) * float(df.loc[i - 1, "ATR14"])
            else:
                stop = math.nan
            if tp_cfg and tp_cfg.get("mode") == "percent":
                tp = entry * (1 + float(tp_cfg["value_pct"]) / 100)
            elif tp_cfg and tp_cfg.get("mode") == "adaptive_risk_atr":
                _, tp = _adaptive_levels(df, i - 1, entry, cfg)
            elif name == "S4_channel_rebound":
                target = tp_cfg.get("tp2", "channel_upper_band")
                tp = float(df.loc[i - 1, "ChannelUpper" if target == "channel_upper_band" else "ChannelMid"])
            elif tp_cfg and tp_cfg.get("mode") == "moving_average":
                field = str(tp_cfg.get("field", "EMA20"))
                tp = float(df.loc[i - 1, field])
                if tp <= entry:
                    tp = entry + float(tp_cfg.get("fallback_atr_multiple", 1.5)) * \
                        float(df.loc[i - 1, "ATR14"])
            else:
                tp = math.nan
            risk_per_share = entry - stop if math.isfinite(stop) else entry
            risk_budget = cash * risk_pct
            by_risk = math.floor(risk_budget / max(risk_per_share, 1e-12))
            by_cash = math.floor((cash - costs["commission_fixed"]) /
                                 (entry * (1 + costs["commission_pct"])))
            qty = max(0, min(by_risk, by_cash))
            if name == "S0_buyhold":
                qty = by_cash
            entry_cost = _commission(entry * qty, costs)
            cash -= entry * qty + entry_cost
            entry_date = str(pd.Timestamp(row.Date).date())

        if qty:
            ambiguous = math.isfinite(stop) and math.isfinite(tp) and row.Low <= stop and row.High >= tp
            exit_price, reason = None, None
            # Daily OHLC cannot reveal ordering: pessimistic stop-first policy.
            if math.isfinite(stop) and row.Low <= stop:
                exit_price, reason = stop, "stop_loss"
            elif math.isfinite(tp) and row.High >= tp:
                exit_price, reason = tp, "take_profit"
            elif trail_cfg:
                trail_pct = float(trail_cfg.get(ticker, trail_cfg.get("default", 12.0))) / 100
                stop = max(stop if math.isfinite(stop) else 0.0,
                           float(row.Close) * (1 - trail_pct))
            if exit_price is not None:
                exit_fill = _fill(float(exit_price), "sell", costs)
                exit_cost = _commission(exit_fill * qty, costs)
                gross = (exit_fill - entry) * qty
                taxable = max(0.0, gross - entry_cost - exit_cost)
                tax = taxable * costs["tax"]
                pnl = gross - entry_cost - exit_cost - tax
                cash += exit_fill * qty - exit_cost - tax
                trades.append(Trade(
                    ticker, name, entry_date, entry,
                    str(pd.Timestamp(row.Date).date()), exit_fill, qty, reason, pnl,
                    (pnl / (entry * qty) * 100) if qty else 0.0, bool(ambiguous)
                ))
                qty, entry, stop, tp = 0, 0.0, math.nan, math.nan
        equity.append(cash + qty * float(row.Close))

    if qty:
        row = df.iloc[-1]
        exit_fill = _fill(float(row.Close), "sell", costs)
        exit_cost = _commission(exit_fill * qty, costs)
        gross = (exit_fill - entry) * qty
        taxable = max(0.0, gross - entry_cost - exit_cost)
        tax = taxable * costs["tax"]
        pnl = gross - entry_cost - exit_cost - tax
        cash += exit_fill * qty - exit_cost - tax
        trades.append(Trade(
            ticker, name, entry_date, entry, str(pd.Timestamp(row.Date).date()),
            exit_fill, qty, "end_of_data", pnl,
            pnl / (entry * qty) * 100, False
        ))
        equity[-1] = cash

    return pd.Series(equity, index=pd.to_datetime(df.Date)), trades


def _single_run(prices: pd.DataFrame, name: str, cfg: dict, general: dict) -> dict:
    initial = float(general.get("capital_eur", 10000.0))
    tickers = prices["Ticker"].dropna().unique().tolist()
    allocation = initial / max(1, len(tickers))
    curves, trades = [], []
    for ticker in tickers:
        data = prices.loc[prices["Ticker"] == ticker].sort_values("Date")
        curve, ticker_trades = _simulate_ticker(data, ticker, name, cfg, general, allocation)
        curves.append(curve)
        trades.extend(ticker_trades)
    curve_df = pd.concat(curves, axis=1).sort_index().ffill()
    equity = curve_df.sum(axis=1)
    evaluation = general.get("evaluation", {})
    if evaluation.get("start"):
        equity = equity.loc[equity.index >= pd.Timestamp(evaluation["start"])]
    if evaluation.get("end"):
        equity = equity.loc[equity.index <= pd.Timestamp(evaluation["end"])]
    if equity.empty:
        raise ValueError("Evaluation period contains no observations")
    returns = equity.pct_change().fillna(0)
    if evaluation.get("start"):
        trades = [t for t in trades if pd.Timestamp(t.entry_date) >= pd.Timestamp(evaluation["start"])]
    if evaluation.get("end"):
        trades = [t for t in trades if pd.Timestamp(t.exit_date) <= pd.Timestamp(evaluation["end"])]
    kpis = {
        "Sharpe": sharpe(returns), "MaxDD": max_drawdown(equity),
        "Calmar": calmar(returns, equity),
        "ProfitFactor": profit_factor(pd.Series([t.pnl for t in trades], dtype=float)),
        "CAGR_sim": float((equity.iloc[-1] / equity.iloc[0]) ** (252 / max(1, len(equity))) - 1),
        "Trades": len(trades),
        "WinRate": float(sum(t.pnl > 0 for t in trades) / len(trades)) if trades else 0.0,
        "AmbiguousBars": sum(t.ambiguous_bar for t in trades),
    }
    benchmark_ticker = general.get("benchmark_ticker", "SWDA.MI")
    close_frame = prices.pivot_table(
        index="Date", columns="Ticker", values="Close", aggfunc="last"
    ).sort_index().ffill()
    close_frame.index = pd.to_datetime(close_frame.index)
    close_frame = close_frame.reindex(equity.index).ffill().bfill()
    normalized = close_frame.div(close_frame.iloc[0]).mul(initial / max(1, len(close_frame.columns)))
    buy_hold = normalized.sum(axis=1)
    benchmark_name = benchmark_ticker if benchmark_ticker in close_frame else close_frame.columns[0]
    benchmark = close_frame[benchmark_name].div(close_frame[benchmark_name].iloc[0]).mul(initial)
    curves = pd.DataFrame({
        "Date": equity.index,
        "Strategy": equity.to_numpy(),
        "Benchmark": benchmark.to_numpy(),
        "BuyHold": buy_hold.to_numpy(),
    })
    return {"equity_curve": equity.tolist(), "curves": curves,
            "benchmark_ticker": benchmark_name, "kpis": kpis,
            "trades": [asdict(t) for t in trades],
            "orders": latest_orders(prices, name, cfg, general)}


def _add_s3_context(prices: pd.DataFrame, cfg: dict,
                    benchmark_ticker: str) -> pd.DataFrame:
    """Build point-in-time S3 filters from the validated OHLCV universe.

    Historical NAV premiums and quoted bid/ask spreads cannot be reconstructed
    from OHLCV data. S3 therefore uses transparent, reproducible proxies that
    are known on each date: trend, benchmark regime, cross-sectional breadth,
    and trailing traded-value liquidity.
    """
    out = prices.sort_values(["Ticker", "Date"]).copy()
    filters = cfg.get("filters", {})
    trend_cfg = filters.get("trend", {})
    regime_cfg = filters.get("regime", {})
    breadth_cfg = filters.get("breadth", {})
    liquidity_cfg = filters.get("liquidity", {})

    trend_ma = int(trend_cfg.get("ma_period", 200))
    breadth_ma = int(breadth_cfg.get("ma_period", 200))
    regime_ma = int(regime_cfg.get("ma_period", 200))
    min_breadth = float(breadth_cfg.get("min_fraction_above_ma", 0.55))
    min_eligible = int(breadth_cfg.get("min_eligible_etfs", 30))
    adv_window = int(liquidity_cfg.get("adv_window", 20))
    min_adv = float(liquidity_cfg.get("min_adv_eur", 100000))
    max_zero_fraction = float(
        liquidity_cfg.get("max_zero_volume_fraction", 0.20)
    )
    if not (0 <= min_breadth <= 1 and 0 <= max_zero_fraction <= 1):
        raise ValueError("Invalid S3 fraction threshold")
    if min(trend_ma, breadth_ma, regime_ma, min_eligible, adv_window) < 1:
        raise ValueError("Invalid S3 rolling window")

    by_ticker = out.groupby("Ticker", group_keys=False)
    out["_S3TrendMA"] = by_ticker["Close"].transform(
        lambda s: s.rolling(trend_ma, min_periods=trend_ma).mean()
    )
    out["_S3SMA50"] = by_ticker["Close"].transform(
        lambda s: s.rolling(50, min_periods=50).mean()
    )
    out["_S3SMA50Slope"] = by_ticker["_S3SMA50"].transform(
        lambda s: s.pct_change(10, fill_method=None)
    )
    out["S3TrendOK"] = out["Close"].gt(out["_S3TrendMA"])
    if bool(trend_cfg.get("require_positive_sma50_slope", True)):
        out["S3TrendOK"] &= out["_S3SMA50Slope"].gt(0)

    close = out.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    breadth_ma_frame = close.rolling(
        breadth_ma, min_periods=breadth_ma
    ).mean()
    eligible = breadth_ma_frame.notna() & close.notna()
    fraction = close.gt(breadth_ma_frame).sum(axis=1).div(
        eligible.sum(axis=1).replace(0, np.nan)
    )
    breadth_ok = fraction.ge(min_breadth) & eligible.sum(axis=1).ge(min_eligible)
    out["S3BreadthOK"] = out["Date"].map(breadth_ok).fillna(False)

    benchmark = str(regime_cfg.get("benchmark", benchmark_ticker))
    if benchmark in close.columns:
        benchmark_close = close[benchmark]
        benchmark_ma_series = benchmark_close.rolling(
            regime_ma, min_periods=regime_ma
        ).mean()
        regime_ok = benchmark_close.gt(benchmark_ma_series)
    else:
        # A missing benchmark must not silently disable S3. Cross-sectional
        # breadth is the explicit, reproducible fallback already in the data.
        regime_ok = breadth_ok
    out["S3RegimeOK"] = out["Date"].map(regime_ok).fillna(False)

    out["_S3TradedValue"] = out["Close"] * out["Volume"]
    out["_S3ZeroVolume"] = out["Volume"].le(0).astype(float)
    out["_S3ADV"] = by_ticker["_S3TradedValue"].transform(
        lambda s: s.rolling(adv_window, min_periods=adv_window).mean()
    )
    out["_S3ZeroFraction"] = by_ticker["_S3ZeroVolume"].transform(
        lambda s: s.rolling(adv_window, min_periods=adv_window).mean()
    )
    out["S3LiquidityOK"] = (
        out["_S3ADV"].ge(min_adv) &
        out["_S3ZeroFraction"].le(max_zero_fraction)
    )
    return out.drop(columns=[
        "_S3TrendMA", "_S3SMA50", "_S3SMA50Slope", "_S3TradedValue",
        "_S3ZeroVolume", "_S3ADV", "_S3ZeroFraction",
    ])


def latest_orders(prices: pd.DataFrame, name: str, cfg: dict, general: dict) -> list[dict]:
    """Produce operational proposals from the exact same strategy rules."""
    if name == "S0_buyhold":
        return []
    orders = []
    capital = float(general.get("capital_eur", 10000))
    risk_pct = float(cfg.get("risk", {}).get(
        "risk_per_trade_pct",
        general.get("risk", {}).get("default_risk_per_trade_pct", 1.0)
    )) / 100
    for ticker, raw in prices.groupby("Ticker"):
        df = enrich(raw.sort_values("Date").reset_index(drop=True))
        signal = _strategy_signals(df, name, cfg)
        if df.empty or not bool(signal.iloc[-1]):
            continue
        row = df.iloc[-1]
        entry = float(row.Close)  # indicative; execution is next open in backtest
        if cfg.get("stop_loss", {}).get("mode") == "adaptive_atr_structure":
            stop, tp1 = _adaptive_levels(df, len(df) - 1, entry, cfg)
            tp2 = tp1
            reason = f"{cfg.get('entry', {}).get('mode', name)}_adaptive_levels"
        elif name == "S4_channel_rebound":
            stop = min(float(row.Low), float(row.ChannelLower)) - \
                float(cfg["stop_loss"].get("atr_multiplier", 0.6)) * float(row.ATR14)
            tp1, tp2 = float(row.ChannelMid), float(row.ChannelUpper)
            reason = "confirmed_descending_channel_rebound"
        elif cfg.get("stop_loss", {}).get("mode") == "signal_low_atr":
            stop = float(row.Low) - float(
                cfg["stop_loss"].get("atr_multiplier", 0.5)
            ) * float(row.ATR14)
            tp_cfg = cfg.get("take_profit", {})
            if tp_cfg.get("mode") == "moving_average":
                tp1 = float(row[str(tp_cfg.get("field", "EMA20"))])
                if tp1 <= entry:
                    tp1 = entry + float(tp_cfg.get("fallback_atr_multiple", 1.5)) * float(row.ATR14)
            else:
                tp1 = entry * (1 + float(tp_cfg.get("value_pct", 10.0)) / 100)
            tp2 = entry + float(tp_cfg.get("tp2_atr_multiple", 3.0)) * float(row.ATR14)
            reason = str(cfg.get("entry", {}).get("mode", name))
        elif cfg.get("stop_loss", {}).get("mode") == "breakdown_low_atr":
            stop = float(row.FalseBreakdownLow) - float(
                cfg["stop_loss"].get("atr_multiplier", 0.25)
            ) * float(row.ATR14)
            tp_cfg = cfg.get("take_profit", {})
            tp1 = float(row[str(tp_cfg.get("field", "EMA20"))])
            if tp1 <= entry:
                tp1 = entry + float(
                    tp_cfg.get("fallback_atr_multiple", 2.0)
                ) * float(row.ATR14)
            tp2 = entry + float(tp_cfg.get("tp2_atr_multiple", 3.0)) * float(row.ATR14)
            reason = "confirmed_false_breakdown_reclaim"
        else:
            stop = entry * (1 - float(cfg["stop_loss"]["value_pct"]) / 100)
            tp1 = entry * (1 + float(cfg["take_profit"]["value_pct"]) / 100)
            tp2 = tp1
            reason = str(cfg.get("entry", {}).get("mode", "confirmed_breakout"))
        risk_share = max(entry - stop, 1e-12)
        size = max(0, math.floor(capital * risk_pct / risk_share))
        orders.append({
            "Ticker": ticker, "SignalDate": str(pd.Timestamp(row.Date).date()),
            "Entry": entry, "EntryType": "next_open_market",
            "Stop": stop, "TP1": tp1, "TP2": tp2, "Size": size,
            "RiskRewardTP1": (tp1 - entry) / risk_share,
            "RiskRewardTP2": (tp2 - entry) / risk_share,
            "Reason": reason,
        })
    return orders


def run_backtest(prices: pd.DataFrame, config: dict) -> dict:
    # Compatibility for the original compact configuration used by older
    # callers and dashboards. New configurations are routed through `runs`.
    if "runs" not in config:
        from .strategy import signal_breakout

        initial = 10000.0
        strategy_returns, buy_hold_returns = [], []
        normalized = normalize_prices(prices)
        normalized["Date"] = pd.to_datetime(normalized["Date"])
        params = config.get("params", {})
        for ticker in normalized["Ticker"].unique().tolist():
            frame = normalized.loc[normalized["Ticker"] == ticker].sort_values(
                "Date").reset_index(drop=True)
            signal = signal_breakout(
                frame,
                atr_pct=params.get("atr_pct", 1),
                buffer_mult=params.get("buffer_mult", 1),
                vol_z_min=params.get("vol_z_min", -3),
            )
            frame = frame.merge(signal, on=["Date", "Close"], how="left")
            position = frame["Entry"].notna().astype(int).shift(1).fillna(0)
            raw = frame.set_index("Date")["Close"].pct_change().fillna(0)
            strategy_returns.append(
                raw.mul(pd.Series(position.to_numpy(), index=frame["Date"])).rename(ticker))
            buy_hold_returns.append(raw.rename(ticker))
        strategy_frame = pd.concat(strategy_returns, axis=1)
        hold_frame = pd.concat(buy_hold_returns, axis=1)
        returns = strategy_frame.mean(axis=1, skipna=True).fillna(0)
        hold_returns = hold_frame.mean(axis=1, skipna=True).fillna(0)
        benchmark_ticker = config.get("benchmark_ticker", "SWDA.MI")
        benchmark_returns = (
            hold_frame[benchmark_ticker]
            if benchmark_ticker in hold_frame else hold_frame.iloc[:, 0]
        ).reindex(returns.index).fillna(0)
        strategy_curve = (1 + returns).cumprod() * initial
        buy_hold_curve = (1 + hold_returns).cumprod() * initial
        benchmark_curve = (1 + benchmark_returns).cumprod() * initial
        curves = pd.DataFrame({
            "Date": returns.index,
            "Strategy": strategy_curve.to_numpy(),
            "Benchmark": benchmark_curve.to_numpy(),
            "BuyHold": buy_hold_curve.to_numpy(),
        })
        return {
            "equity_curve": strategy_curve.tolist(),
            "curves": curves,
            "benchmark_ticker": benchmark_ticker,
            "kpis": {
                "Sharpe": sharpe(returns),
                "MaxDD": max_drawdown(strategy_curve),
                "Calmar": calmar(returns, strategy_curve),
                "ProfitFactor": profit_factor(returns),
                "CAGR_sim": (
                    (strategy_curve.iloc[-1] / strategy_curve.iloc[0])
                    ** (252 / max(1, len(strategy_curve))) - 1
                ),
            },
        }

    prices = normalize_prices(prices)
    prices["Date"] = pd.to_datetime(prices["Date"], utc=True).dt.tz_localize(None)
    general = {
        **config.get("general", {}),
        "benchmark_ticker": config.get("benchmark_ticker", "SWDA.MI"),
    }
    quality = validate_prices(prices, bool(general.get("data", {}).get("strict_quality", True)))
    active = config.get("active_run", "S1_breakout")
    runs = config.get("runs", {})
    if active in {"all", "S3_breakout_checklist"} and \
            "S3_breakout_checklist" in runs:
        prices = _add_s3_context(
            prices, runs["S3_breakout_checklist"],
            str(general.get("benchmark_ticker", "SWDA.MI")),
        )
    if active == "all":
        results = {}
        for name, cfg in runs.items():
            if name == "S2_multilayer":
                all_cfg = {**config, "active_run": name}
                results[name] = run_backtest(prices, all_cfg)
                continue
            results[name] = _single_run(prices, name, cfg, general)
        return {"runs": results, "data_quality": quality}
    if active == "S2_multilayer":
        cfg = runs[active]
        core_weight = float(cfg.get("capital_weights", {}).get("core_pct", 70.0)) / 100
        tactical_weight = 1 - core_weight
        total_capital = float(general.get("capital_eur", 10000))
        core_capital = total_capital * core_weight
        tactical_general = {**general, "capital_eur": float(general.get("capital_eur", 10000)) * tactical_weight}
        tranches = cfg["core"].get("scaling_tranches", [])
        if not tranches or abs(sum(float(t["weight_pct"]) for t in tranches) - 100.0) > 1e-6:
            raise ValueError("S2 core tranche weights must sum to 100")
        core_runs = []
        for tranche in tranches:
            weight = float(tranche["weight_pct"]) / 100
            tranche_general = {**general, "capital_eur": core_capital * weight}
            mode = tranche["mode"]
            common = {
                "exit": {"trailing_pct_by_ticker": cfg["core"]["trailing_pct_by_ticker"]},
                "risk": {"risk_per_trade_pct": 100.0},
            }
            if mode == "market_now":
                run_name = "S0_buyhold"
                tranche_cfg = {**common, "entry": {"mode": "market_open_next"}}
            elif mode == "pullback_dma":
                run_name = "S2_core_pullback"
                tranche_cfg = {
                    **common,
                    "entry": {
                        "mode": "trend_pullback",
                        "tolerance_atr": tranche.get("tolerance_atr", 0.35),
                        "rsi_min": tranche.get("rsi_min", 30),
                        "rsi_max": tranche.get("rsi_max", 55),
                    },
                    "stop_loss": {
                        "mode": "signal_low_atr",
                        "atr_multiplier": tranche.get("stop_atr_multiplier", 0.6),
                    },
                }
            elif mode == "multi_horizon_breakout":
                run_name = "S2_core_breakout"
                tranche_cfg = {
                    **common,
                    "entry": {
                        "mode": mode,
                        "lookback_days": tranche.get("lookback_days", [63, 126, 252]),
                        "min_confirmations": tranche.get("min_confirmations", 2),
                        "buffer_pct": tranche.get("buffer_pct", 0.3),
                    },
                    "stop_loss": {
                        "mode": "adaptive_atr_structure",
                        "lookback_days": tranche.get("stop_lookback_days", 20),
                        "atr_multiple": tranche.get("stop_atr_multiple", 2.5),
                        "structure_buffer_atr": tranche.get("structure_buffer_atr", 0.25),
                    },
                }
            else:
                raise ValueError(f"Unsupported S2 tranche mode: {mode}")
            core_runs.append(_single_run(prices, run_name, tranche_cfg,
                                         tranche_general))
        tactical_cfg = {
            "entry": cfg["tactical"]["entry"],
            "stop_loss": cfg["tactical"]["stop_loss"],
            "take_profit": cfg["tactical"]["take_profit"],
        }
        tactical = _single_run(prices, "S1_breakout", tactical_cfg, tactical_general)
        # Every tranche has its own ledger; no exit can affect another layer.
        layers = core_runs + [tactical]
        n = min(len(layer["equity_curve"]) for layer in layers)
        equity = sum(
            (pd.Series(layer["equity_curve"][-n:]) for layer in layers),
            start=pd.Series(np.zeros(n)),
        )
        returns = equity.pct_change().fillna(0)
        trades = [trade for layer in layers for trade in layer["trades"]]
        pnl = pd.Series([t["pnl"] for t in trades], dtype=float)
        result = {
            "equity_curve": equity.tolist(),
            "trades": trades,
            "kpis": {
                "Sharpe": sharpe(returns), "MaxDD": max_drawdown(equity),
                "Calmar": calmar(returns, equity), "ProfitFactor": profit_factor(pnl),
                "CAGR_sim": float((equity.iloc[-1] / equity.iloc[0]) ** (252 / max(1, len(equity))) - 1),
                "Trades": len(trades),
                "WinRate": float((pnl > 0).mean()) if len(pnl) else 0.0,
                "AmbiguousBars": sum(t["ambiguous_bar"] for t in trades),
            },
            "data_quality": quality, "active_run": active,
            "layers": {
                "core_tranches": [layer["kpis"] for layer in core_runs],
                "tactical": tactical["kpis"],
            },
            "orders": [order for layer in layers for order in layer["orders"]],
        }
        return result
    result = _single_run(prices, active, runs[active], general)
    result["data_quality"] = quality
    result["active_run"] = active
    return result
