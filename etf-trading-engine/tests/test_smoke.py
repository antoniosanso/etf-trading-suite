from src.engine.metrics import sharpe, max_drawdown, calmar, profit_factor
import pandas as pd

def test_metrics_smoke():
    r = pd.Series([0.0, 0.01, -0.005, 0.002])
    eq = (1+r).cumprod()*100
    assert -1.0 <= max_drawdown(eq) <= 0.0
    assert profit_factor(r) > 0.0
    _ = sharpe(r); _ = calmar(r, eq)
