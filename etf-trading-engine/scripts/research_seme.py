"""Robust, ETF-specific research for SEME.MI.

This module intentionally keeps the parameter space small and applies signals
with a one-session delay. It is research-only: it cannot approve live orders.
"""
from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Params:
    slow_ma: int
    slope_days: int
    core_weight: float
    fast_ema: int
    pullback_atr: float
    tactical_hold: int


def load_prices(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Date"]).sort_values("Date")
    required = {"Date", "Open", "High", "Low", "Close", "Volume"}
    if missing := required - set(df):
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if df.duplicated("Date").any() or df[list(required - {"Date"})].isna().any().any():
        raise ValueError("SEME data contain duplicates or missing values")
    if (df[["Open", "High", "Low", "Close"]] <= 0).any().any():
        raise ValueError("SEME data contain non-positive prices")
    return df.reset_index(drop=True)


def indicators(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    out = df.copy()
    previous = out["Close"].shift()
    tr = pd.concat([
        out["High"] - out["Low"],
        (out["High"] - previous).abs(),
        (out["Low"] - previous).abs(),
    ], axis=1).max(axis=1)
    out["ATR14"] = tr.rolling(14).mean()
    out["SlowMA"] = out["Close"].rolling(p.slow_ma).mean()
    out["FastEMA"] = out["Close"].ewm(span=p.fast_ema, adjust=False).mean()
    out["Trend"] = (
        (out["Close"] > out["SlowMA"]) &
        (out["SlowMA"].pct_change(p.slope_days, fill_method=None) > 0)
    )
    touched = out["Low"] <= out["FastEMA"] + p.pullback_atr * out["ATR14"]
    recovery = (
        touched.shift(1, fill_value=False).astype(bool) &
        (out["Close"] > out["FastEMA"]) &
        (out["Close"] > out["Open"]) &
        out["Trend"]
    )
    tactical = pd.Series(False, index=out.index)
    remaining = 0
    for i in out.index:
        if not bool(out.loc[i, "Trend"]):
            remaining = 0
        elif bool(recovery.loc[i]):
            remaining = p.tactical_hold
        tactical.loc[i] = remaining > 0
        remaining = max(0, remaining - 1)
    out["SignalExposure"] = (
        p.core_weight * out["Trend"].astype(float) +
        (1 - p.core_weight) * tactical.astype(float)
    ).clip(0, 1)
    # Today's close can only affect exposure from the next session.
    out["Exposure"] = out["SignalExposure"].shift(1).fillna(0)
    return out


def simulate(df: pd.DataFrame, p: Params, start: str, end: str,
             capital: float = 105_000.0, one_way_drag: float = 0.002,
             commission: float = 2.95, tax_rate: float = 0.26) -> dict:
    work = indicators(df, p)
    mask = work["Date"].between(start, end)
    work = work.loc[mask].copy()
    if work.empty:
        raise ValueError("Empty evaluation window")
    cash, shares, average_cost = capital, 0.0, 0.0
    equity_values, trade_events = [], 0
    for row in work.itertuples():
        open_price = float(row.Open)
        desired_value = float(row.Exposure) * (
            cash + shares * open_price
        )
        current_value = shares * open_price
        delta = desired_value - current_value
        if abs(delta) > max(commission * 2, capital * 1e-6):
            trade_events += 1
            if delta > 0:
                fill = open_price * (1 + one_way_drag)
                affordable = max(0.0, cash - commission)
                bought = min(delta, affordable) / fill
                old_cost = average_cost * shares
                cash -= bought * fill + commission
                shares += bought
                average_cost = (
                    (old_cost + bought * fill) / shares if shares else 0.0
                )
            else:
                fill = open_price * (1 - one_way_drag)
                sold = min(shares, -delta / fill)
                gross_gain = (fill - average_cost) * sold
                tax = max(0.0, gross_gain) * tax_rate
                cash += sold * fill - commission - tax
                shares -= sold
                if shares < 1e-10:
                    shares, average_cost = 0.0, 0.0
        equity_values.append(cash + shares * float(row.Close))
    equity = pd.Series(equity_values, index=work.index) / capital
    net = equity.pct_change().fillna(equity.iloc[0] - 1)
    peak = equity.cummax()
    drawdown = equity / peak - 1
    years = max(len(work) / 252, 1 / 252)
    total = float(equity.iloc[-1] - 1)
    cagr = float(equity.iloc[-1] ** (1 / years) - 1)
    volatility = float(net.std(ddof=0) * np.sqrt(252))
    sharpe = float(net.mean() * 252 / (volatility + 1e-12))
    maxdd = float(drawdown.min())
    calmar = cagr / (abs(maxdd) + 1e-12)
    buyhold = float(work["Close"].iloc[-1] / work["Open"].iloc[0] - 1)
    return {
        "return": total, "cagr": cagr, "sharpe": sharpe,
        "maxdd": maxdd, "calmar": calmar, "trades": trade_events,
        "buyhold": buyhold, "exposure": float(work["Exposure"].mean()),
    }


def score(windows: list[dict]) -> float:
    returns = np.array([w["return"] for w in windows])
    sharpes = np.array([w["sharpe"] for w in windows])
    drawdowns = np.array([abs(w["maxdd"]) for w in windows])
    positive = float((returns > 0).mean())
    # Reward the weakest period and consistency; penalize drawdown and dispersion.
    return float(
        returns.mean() + 0.75 * returns.min() - 0.5 * returns.std()
        + 0.02 * sharpes.mean() + 0.04 * positive - 0.35 * drawdowns.mean()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    df = load_prices(args.prices)
    development = [
        ("2022", "2022-01-01", "2022-12-31"),
        ("2023", "2023-01-01", "2023-12-31"),
        ("2024", "2024-01-01", "2024-12-31"),
        ("2025", "2025-01-01", "2025-12-31"),
    ]
    final = ("2026", "2026-01-01", str(df["Date"].max().date()))
    candidates = []
    grid = itertools.product(
        [100, 150, 200], [10, 20], [0.5, 0.65, 0.8, 1.0],
        [10, 20], [0.0, 0.5], [3, 5, 10],
    )
    for values in grid:
        p = Params(*values)
        windows = [
            {"window": name, **simulate(df, p, start, end)}
            for name, start, end in development
        ]
        candidates.append((score(windows), p, windows))
    candidates.sort(key=lambda item: item[0], reverse=True)

    # Stability check around the leading solutions: select the member whose
    # immediate parameter neighbourhood also performs well.
    top = candidates[:30]
    robust = []
    for base_score, p, windows in top:
        neighbours = [
            item[0] for item in candidates
            if item[1].slow_ma == p.slow_ma
            and item[1].fast_ema == p.fast_ema
            and abs(item[1].core_weight - p.core_weight) <= 0.15
            and item[1].tactical_hold in {
                max(3, p.tactical_hold - 2), p.tactical_hold,
                p.tactical_hold + 2,
            }
        ]
        neighbourhood = float(np.mean(sorted(neighbours, reverse=True)[:5]))
        robust.append((0.7 * base_score + 0.3 * neighbourhood, p, windows))
    robust.sort(key=lambda item: item[0], reverse=True)
    robust_score, selected, dev_windows = robust[0]
    final_result = {"window": final[0], **simulate(df, selected, final[1], final[2])}
    stressed = simulate(
        df, selected, "2022-01-01", final[2],
        one_way_drag=0.003, commission=5.90,
    )
    result = {
        "symbol": "SEME.MI",
        "data_start": str(df["Date"].min().date()),
        "data_end": str(df["Date"].max().date()),
        "method": "development 2022-2025; untouched final check 2026",
        "selected": asdict(selected),
        "robust_score": robust_score,
        "development": dev_windows,
        "final_check": final_result,
        "stress_2023_to_end": stressed,
        "top_candidates": [
            {"score": s, "params": asdict(p), "windows": windows}
            for s, p, windows in robust[:10]
        ],
        "live_status": "RESEARCH_ONLY",
    }
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
