import pandas as pd

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df['High'], df['Low'], df['Close']
    prev_close = close.shift(1)
    tr = (high - low).abs().combine((high - prev_close).abs(), max).combine((low - prev_close).abs(), max)
    return tr.rolling(period, min_periods=period).mean()

def zscore(series: pd.Series, window: int = 20) -> pd.Series:
    rolling = series.rolling(window, min_periods=window)
    return (series - rolling.mean()) / (rolling.std(ddof=0) + 1e-12)
