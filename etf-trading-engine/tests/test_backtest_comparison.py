import pandas as pd

from src.engine.backtest import run_backtest


def test_backtest_returns_aligned_comparison_curves():
    dates = pd.date_range("2025-01-01", periods=30)
    rows = []
    for ticker, offset in (("AAA", 0), ("BBB", 10)):
        for i, date in enumerate(dates):
            close = 100 + offset + i
            rows.append({"Date": date, "Ticker": ticker, "Open": close,
                         "High": close + 1, "Low": close - 1, "Close": close,
                         "Volume": 1000 + i})
    config = {"params": {"atr_pct": 1, "buffer_mult": 1, "vol_z_min": -3},
              "benchmark_ticker": "BBB"}
    result = run_backtest(pd.DataFrame(rows), config)
    assert list(result["curves"].columns) == ["Date", "Strategy", "Benchmark", "BuyHold"]
    assert len(result["curves"]) == len(dates)
    assert result["benchmark_ticker"] == "BBB"
