import pandas as pd
import numpy as np

def load_dataset(path):
    df = pd.read_csv(path)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

def pivot_close(df):
    return df.pivot_table(index='Date', columns='Ticker', values='Close').sort_index()

def daily_returns(prices):
    return prices.pct_change().dropna(how='all')

def build_portfolio(returns, weights):
    w = pd.Series(weights, index=returns.columns).astype(float)
    w = w.reindex(returns.columns).fillna(0.0)
    port = (returns * w).sum(axis=1)
    return port

def kpis(series, periods=252):
    r = series.dropna()
    if r.empty:
        return {"CAGR":0,"Sharpe":0,"Vol":0,"MaxDD":0}
    eq = (1+r).cumprod()
    cagr = (eq.iloc[-1]/eq.iloc[0])**(periods/len(eq)) - 1.0
    sharpe = (r.mean()*periods) / (r.std(ddof=0)*np.sqrt(periods) + 1e-12)
    peak = eq.cummax()
    mdd = (eq/peak - 1.0).min()
    return {"CAGR":float(cagr),"Sharpe":float(sharpe),"Vol":float(r.std(ddof=0)*np.sqrt(periods)),"MaxDD":float(mdd)}

def corr_matrix(returns):
    return returns.corr()
