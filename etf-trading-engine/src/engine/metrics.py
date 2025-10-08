import numpy as np
import pandas as pd

def sharpe(returns: pd.Series, rf: float = 0.0, periods: int = 252) -> float:
    er = returns.mean()*periods - rf
    vol = returns.std(ddof=0)*np.sqrt(periods) + 1e-12
    return float(er/vol)

def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity/peak - 1.0).min()
    return float(dd)

def calmar(returns: pd.Series, equity: pd.Series, periods: int = 252) -> float:
    cagr = (equity.iloc[-1]/equity.iloc[0])**(periods/len(equity)) - 1.0
    mdd = abs(max_drawdown(equity))
    return float(cagr / (mdd + 1e-12))

def profit_factor(gains: pd.Series) -> float:
    pos = gains[gains>0].sum()
    neg = -gains[gains<0].sum()
    return float(pos / (neg + 1e-12))
