"""Strategy primitives shared by backtests and operational signals."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import atr, zscore


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("Date").copy()
    out["ATR14"] = atr(out, 14)
    out["RSI14"] = _rsi(out["Close"], 14)
    out["VolZ20"] = zscore(out["Volume"].astype(float), 20)
    out["SMA20"] = out["Close"].rolling(20).mean()
    out["SMA50"] = out["Close"].rolling(50).mean()
    out["SMA200"] = out["Close"].rolling(200).mean()
    out["EMA20"] = out["Close"].ewm(span=20, adjust=False).mean()
    out["SMA50Slope"] = out["SMA50"].pct_change(10, fill_method=None)
    out["Return5"] = out["Close"].pct_change(5)
    out["CloseZ20"] = (
        (out["Close"] - out["Close"].rolling(20).mean()) /
        out["Close"].rolling(20).std(ddof=0).replace(0, np.nan)
    )
    return out


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - 100 / (1 + up / down.replace(0, np.nan))


def breakout_entries(df: pd.DataFrame, lookback: int = 252, buffer_pct: float = 0.3,
                     volume_z_min: float | None = None) -> pd.Series:
    """Signal on a close above the *previous* rolling high (no look-ahead)."""
    threshold = df["High"].shift(1).rolling(lookback, min_periods=lookback).max()
    signal = df["Close"] >= threshold * (1 + buffer_pct / 100)
    if volume_z_min is not None:
        signal &= df["VolZ20"] >= volume_z_min
    return signal.fillna(False)


def multi_horizon_breakout_entries(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Require agreement across independently specified prior-high horizons."""
    horizons = [int(v) for v in cfg.get("lookback_days", [20, 63, 126, 252])]
    required = int(cfg.get("min_confirmations", 2))
    if not horizons or required < 1 or required > len(horizons):
        raise ValueError("Invalid multi-horizon breakout configuration")
    votes = pd.concat([
        breakout_entries(df, h, float(cfg.get("buffer_pct", 0.0)),
                         cfg.get("volume_z_min"))
        for h in horizons
    ], axis=1)
    signal = votes.sum(axis=1) >= required
    if bool(cfg.get("trend_filter", True)):
        signal &= (df["Close"] > df["SMA200"]) & (df["SMA50Slope"] > 0)
    return signal.fillna(False)


def trend_pullback_entries(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Confirmed recovery from EMA20/SMA50 inside a valid rising trend."""
    tolerance = float(cfg.get("tolerance_atr", 0.35))
    rsi_min = float(cfg.get("rsi_min", 30.0))
    rsi_max = float(cfg.get("rsi_max", 55.0))
    trend = (
        (df["Close"] > df["SMA200"]) &
        (df["SMA50"] > df["SMA200"]) &
        (df["SMA50Slope"] > float(cfg.get("sma50_slope_min", 0.0)))
    )
    near_ema = (df["Low"] <= df["EMA20"] + tolerance * df["ATR14"])
    near_sma = (df["Low"] <= df["SMA50"] + tolerance * df["ATR14"])
    touched = trend & (near_ema | near_sma) & df["RSI14"].between(rsi_min, rsi_max)
    confirmation = (
        touched.shift(1, fill_value=False).astype(bool) &
        (df["Close"] > df["High"].shift(1)) &
        (df["Close"] > df["Open"]) &
        (df["RSI14"] > df["RSI14"].shift(1))
    )
    return confirmation.fillna(False)


def shock_reversion_entries(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Confirmed mean reversion after an ATR-scaled, statistically extreme fall."""
    window = int(cfg.get("shock_window_days", 5))
    shock_atr = float(cfg.get("shock_atr_multiple", 2.5))
    z_max = float(cfg.get("close_z_max", -1.5))
    rsi_max = float(cfg.get("rsi_max", 35.0))
    prior_close = df["Close"].shift(window)
    fall = prior_close - df["Close"]
    shock = (
        (fall >= shock_atr * df["ATR14"]) &
        (df["CloseZ20"] <= z_max) &
        (df["RSI14"] <= rsi_max)
    )
    confirmation_mode = cfg.get("confirmation", "close_above_reversal_high")
    if confirmation_mode == "close_above_reversal_high":
        confirmation = (
            shock.shift(1, fill_value=False).astype(bool) &
            (df["Close"] > df["High"].shift(1)) &
            (df["Close"] > df["Open"]) &
            (df["RSI14"] > df["RSI14"].shift(1))
        )
    else:
        raise ValueError(f"Unsupported shock confirmation: {confirmation_mode}")
    return confirmation.fillna(False)


def descending_channel(df: pd.DataFrame, lookback: int = 45) -> pd.DataFrame:
    """Rolling robust-ish channel based on OLS residual quantiles.

    The fit only uses observations available at each date. Quality rewards a
    negative slope, explanatory power and contacts close to both channel bands.
    """
    result = pd.DataFrame(index=df.index, columns=[
        "ChannelLower", "ChannelMid", "ChannelUpper", "ChannelScore"
    ], dtype=float)
    close = df["Close"].astype(float)
    for end in range(lookback - 1, len(df)):
        y = close.iloc[end - lookback + 1:end + 1].to_numpy()
        x = np.arange(lookback, dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        mid = intercept + slope * x
        residual = y - mid
        lo, hi = np.quantile(residual, [0.10, 0.90])
        fitted = mid[-1]
        ss_tot = np.square(y - y.mean()).sum()
        r2 = 0.0 if ss_tot == 0 else 1 - np.square(residual).sum() / ss_tot
        width = max(hi - lo, 1e-12)
        tolerance = width * 0.15
        lower_contacts = np.count_nonzero(np.abs(residual - lo) <= tolerance)
        upper_contacts = np.count_nonzero(np.abs(residual - hi) <= tolerance)
        contacts = min(1.0, min(lower_contacts, upper_contacts) / 2)
        slope_score = min(1.0, max(0.0, -slope / (y.mean() + 1e-12) * lookback / 0.05))
        score = 0.45 * max(0.0, r2) + 0.30 * contacts + 0.25 * slope_score
        result.iloc[end] = [fitted + lo, fitted, fitted + hi, score]
    return result


def channel_rebound_entries(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Confirmed rebound after touching a statistically fitted lower channel."""
    lookback = int(cfg.get("lookback_days", 45))
    channel = descending_channel(df, lookback)
    for col in channel:
        df[col] = channel[col]
    tolerance = float(cfg.get("lower_band_tolerance_atr", 0.35))
    min_score = float(cfg.get("min_channel_score", 0.70))
    touch = df["Low"] <= df["ChannelLower"] + tolerance * df["ATR14"]
    # Confirmation is deliberately evaluated after the touch, not on it.
    reversal = touch.shift(1, fill_value=False).astype(bool) & (
        df["Close"] > df["High"].shift(1)
    ) & (df["Close"] > df["Open"])
    rsi_recovery = df["RSI14"] > df["RSI14"].shift(1)
    descending = df["ChannelMid"] < df["ChannelMid"].shift(5)
    return (reversal & rsi_recovery & descending &
            (df["ChannelScore"] >= min_score)).fillna(False)


def signal_breakout(df: pd.DataFrame, atr_pct=0.02, buffer_mult=0.10, vol_z_min=0.85):
    """Compatibility wrapper for old callers; now uses prior 20-day high."""
    out = enrich(df)
    high20 = out["High"].shift(1).rolling(20).max()
    out["Entry"] = (high20 + buffer_mult * out["ATR14"]).where(
        breakout_entries(out, 20, 0.0, vol_z_min)
    )
    return out[["Date", "Close", "ATR14", "Entry", "VolZ20"]]
