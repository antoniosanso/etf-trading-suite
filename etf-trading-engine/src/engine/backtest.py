import pandas as pd
import numpy as np
from .strategy import signal_breakout
from .metrics import sharpe, max_drawdown, calmar, profit_factor

def run_backtest(prices: pd.DataFrame, config: dict) -> dict:
    tickers = prices['Ticker'].unique().tolist()
    equity = 10000.0
    strategy_returns = []
    buy_hold_returns = []

    for t in tickers:
        df = prices[prices['Ticker']==t].sort_values('Date').reset_index(drop=True)
        sig = signal_breakout(df,
                              atr_pct=config['params']['atr_pct'],
                              buffer_mult=config['params']['buffer_mult'],
                              vol_z_min=config['params']['vol_z_min'])
        df = df.merge(sig, on=['Date','Close'], how='left')
        df['Position'] = (df['Entry'].notna()).astype(int).shift(1).fillna(0)
        raw_ret = df.set_index('Date')['Close'].pct_change().fillna(0)
        position = pd.Series(df['Position'].to_numpy(), index=df['Date'])
        strategy_returns.append(raw_ret.mul(position).rename(t))
        buy_hold_returns.append(raw_ret.rename(t))

    strategy_frame = pd.concat(strategy_returns, axis=1) if strategy_returns else pd.DataFrame()
    hold_frame = pd.concat(buy_hold_returns, axis=1) if buy_hold_returns else pd.DataFrame()
    returns = strategy_frame.mean(axis=1, skipna=True).fillna(0) if not strategy_frame.empty else pd.Series([0.0])
    hold_returns = hold_frame.mean(axis=1, skipna=True).fillna(0) if not hold_frame.empty else returns
    benchmark_ticker = config.get('benchmark_ticker', 'SWDA.MI')
    if not hold_frame.empty:
        benchmark_returns = hold_frame[benchmark_ticker] if benchmark_ticker in hold_frame else hold_frame.iloc[:, 0]
        benchmark_returns = benchmark_returns.reindex(returns.index).fillna(0)
    else:
        benchmark_returns = returns
    equity_curve = (1+returns).cumprod()*equity
    buy_hold_curve = (1+hold_returns.reindex(returns.index).fillna(0)).cumprod()*equity
    benchmark_curve = (1+benchmark_returns).cumprod()*equity

    kpis = {
        'Sharpe': sharpe(returns),
        'MaxDD': max_drawdown(equity_curve),
        'Calmar': calmar(returns, equity_curve),
        'ProfitFactor': profit_factor(returns),
        'CAGR_sim': (equity_curve.iloc[-1]/equity_curve.iloc[0])**(252/len(equity_curve)) - 1.0
    }
    curves = pd.DataFrame({
        'Date': returns.index,
        'Strategy': equity_curve.to_numpy(),
        'Benchmark': benchmark_curve.to_numpy(),
        'BuyHold': buy_hold_curve.to_numpy(),
    })
    return {'equity_curve': equity_curve.tolist(), 'curves': curves, 'kpis': kpis,
            'benchmark_ticker': benchmark_ticker}
