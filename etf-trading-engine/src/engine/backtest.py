import pandas as pd
import numpy as np
from .strategy import signal_breakout
from .metrics import sharpe, max_drawdown, calmar, profit_factor

def run_backtest(prices: pd.DataFrame, config: dict) -> dict:
    tickers = prices['Ticker'].unique().tolist()
    equity = 10000.0
    daily_returns = []

    for t in tickers:
        df = prices[prices['Ticker']==t].sort_values('Date').reset_index(drop=True)
        sig = signal_breakout(df,
                              atr_pct=config['params']['atr_pct'],
                              buffer_mult=config['params']['buffer_mult'],
                              vol_z_min=config['params']['vol_z_min'])
        df = df.merge(sig, on=['Date','Close'], how='left')
        df['Position'] = (df['Entry'].notna()).astype(int).shift(1).fillna(0)
        ret = df['Close'].pct_change().fillna(0) * df['Position']
        daily_returns.append(ret)

    returns = sum(daily_returns) / max(1,len(daily_returns)) if daily_returns else pd.Series([0.0])
    equity_curve = (1+returns).cumprod()*equity

    kpis = {
        'Sharpe': sharpe(returns),
        'MaxDD': max_drawdown(equity_curve),
        'Calmar': calmar(returns, equity_curve),
        'ProfitFactor': profit_factor(returns),
        'CAGR_sim': (equity_curve.iloc[-1]/equity_curve.iloc[0])**(252/len(equity_curve)) - 1.0
    }
    return {'equity_curve': equity_curve.tolist(), 'kpis': kpis}
