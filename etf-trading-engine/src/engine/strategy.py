import pandas as pd
from .indicators import atr, zscore

def signal_breakout(df: pd.DataFrame, atr_pct=0.02, buffer_mult=0.10, vol_z_min=0.85):
    df = df.copy()
    df['ATR14'] = atr(df, 14)
    df['ATR_pct'] = df['ATR14'] / (df['Close'].rolling(14).mean() + 1e-12)
    df['VolZ20'] = zscore(df['Volume'].astype(float), 20)
    high20 = df['High'].rolling(20).max()
    entry = high20 + buffer_mult * df['ATR14']
    cond = (df['ATR_pct'].between(atr_pct*0.6, atr_pct*1.75)) & (df['VolZ20'] >= vol_z_min)
    df['Entry'] = entry.where(cond)
    return df[['Date','Close','ATR14','Entry','VolZ20']]
