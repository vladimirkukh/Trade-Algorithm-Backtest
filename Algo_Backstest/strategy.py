"""
Author: Vladimir Kukharev
Date: 2026-07-31
Version: 1.1
<Strategy> is responsible for implementing the UT Bot, using an ATR Trailing Stop 
strategy. It provides functions to donwload historical OHLCV data and computes
signals based on the strategy. 

Notes: <interval> value responsible for the freq. of the OHLCV data. 
"""

import yfinance as yf
import pandas as pd
import numpy as np


def get_data(ticker: str, interval: str = "1h",
             period: str = None, start: str = None, end: str = None) -> pd.DataFrame:
    """Download OHLCV data from yfinance."""
    if start and end:
        df = yf.download(ticker, start=start, end=end, interval=interval, progress=False)
    else:
        df = yf.download(ticker, period=period or "3mo", interval=interval, progress=False)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna()
    return df


def compute_signals(df: pd.DataFrame, atr_period: int = 10, sensitivity: float = 1.0) -> pd.DataFrame:
    """
    Implement UT Bot / ATR Trailing Stop strategy.

    Parameters
    ----------
    df          : OHLCV DataFrame (must have High, Low, Close columns)
    atr_period  : Lookback window for ATR calculation
    sensitivity : Multiplier applied to ATR to set the trailing stop distance

    Returns
    -------
    DataFrame with additional columns:
        ATR, TrailingStop, Buy, Sell
    """
    df = df.copy()

    # ----- ATR -----
    df["H-L"]  = df["High"] - df["Low"]
    df["H-PC"] = (df["High"] - df["Close"].shift(1)).abs()
    df["L-PC"] = (df["Low"]  - df["Close"].shift(1)).abs()
    df["TR"]   = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
    df["ATR"]  = df["TR"].rolling(atr_period).mean()

    nLoss = sensitivity * df["ATR"]

    # ----- Trailing Stop (mirrors Pine Script xATRTrailingStop) -----
    trailing = [df["Close"].iloc[0].item()]

    for i in range(1, len(df)):
        price   = df["Close"].iloc[i].item()
        prev_ts = trailing[-1]
        loss    = nLoss.iloc[i].item() if pd.notna(nLoss.iloc[i]) else 0.0
        prev_price = df["Close"].iloc[i - 1].item()

        if price > prev_ts and prev_price > prev_ts:
            trailing.append(max(prev_ts, price - loss))
        elif price < prev_ts and prev_price < prev_ts:
            trailing.append(min(prev_ts, price + loss))
        elif price > prev_ts:
            trailing.append(price - loss)
        else:
            trailing.append(price + loss)

    df["TrailingStop"] = trailing

    # ----- EMA(1) == src (close), used for crossover detection -----
    df["EMA1"] = df["Close"].ewm(span=1, adjust=False).mean()

    above = (df["EMA1"] > df["TrailingStop"]) & (df["EMA1"].shift(1) <= df["TrailingStop"].shift(1))
    below = (df["TrailingStop"] > df["EMA1"]) & (df["TrailingStop"].shift(1) <= df["EMA1"].shift(1))

    df["Buy"]  = (df["Close"] > df["TrailingStop"]) & above
    df["Sell"] = (df["Close"] < df["TrailingStop"]) & below

    return df


def run_backtest(df: pd.DataFrame) -> dict:
    """
    Simulate long-only trades based on Buy / Sell signals.

    Entry  : next open after a Buy signal
    Exit   : next open after a Sell signal  (or last close if no exit)

    Returns
    -------
    dict with keys:
        'equity'  : pd.Series  – daily indexed equity curve starting at 1.0
        'trades'  : pd.DataFrame – one row per completed (or open) trade
        'metrics' : dict – summary stats
    """
    signals = df[df["Buy"] | df["Sell"]].copy()

    trades = []
    in_trade   = False
    entry_date = None
    entry_price = None

    closes = df["Close"]

    for date, row in df.iterrows():
        if not in_trade and row["Buy"]:
            in_trade    = True
            entry_date  = date
            entry_price = float(row["Close"])

        elif in_trade and row["Sell"]:
            exit_date  = date
            exit_price = float(row["Close"])
            pct        = (exit_price - entry_price) / entry_price * 100

            trades.append({
                "Entry Date"  : entry_date,
                "Exit Date"   : exit_date,
                "Entry Price" : round(entry_price, 2),
                "Exit Price"  : round(exit_price,  2),
                "Return (%)"  : round(pct, 2),
                "Status"      : "Closed",
            })
            in_trade = False

    # Open trade still running
    if in_trade:
        exit_price = float(closes.iloc[-1])
        pct        = (exit_price - entry_price) / entry_price * 100
        trades.append({
            "Entry Date"  : entry_date,
            "Exit Date"   : closes.index[-1],
            "Entry Price" : round(entry_price, 2),
            "Exit Price"  : round(exit_price,  2),
            "Return (%)"  : round(pct, 2),
            "Status"      : "Open",
        })

    trades_df = pd.DataFrame(trades)

    # ----- Equity curve (indexed to 1.0) -----
    equity = pd.Series(1.0, index=df.index)
    multiplier = 1.0

    active_entry = None
    for date, row in df.iterrows():
        if not in_trade and row["Buy"]:
            active_entry = float(row["Close"])

        if active_entry is not None:
            equity[date] = multiplier * (float(row["Close"]) / active_entry)

        if row["Sell"] and active_entry is not None:
            multiplier = equity[date]
            active_entry = None

    equity = equity / equity.iloc[0]

    # Rebuild equity properly: compound trade returns
    equity = _build_equity_curve(df, trades_df)

    total_return = round((equity.iloc[-1] - 1) * 100, 2)
    win_trades   = trades_df[trades_df["Return (%)"] > 0] if not trades_df.empty else pd.DataFrame()
    win_rate     = round(len(win_trades) / len(trades_df) * 100, 1) if not trades_df.empty else 0.0

    metrics = {
        "Total Return (%)": total_return,
        "Total Trades"    : len(trades_df),
        "Win Rate (%)"    : win_rate,
    }

    return {"equity": equity, "trades": trades_df, "metrics": metrics}


def _build_equity_curve(df: pd.DataFrame, trades_df: pd.DataFrame) -> pd.Series:
    """
    Build a smooth equity curve that stays flat between trades
    and compounds each completed trade's return.
    """
    equity = pd.Series(np.nan, index=df.index)
    equity.iloc[0] = 1.0

    capital = 1.0

    if trades_df.empty:
        equity = equity.ffill().fillna(1.0)
        return equity

    for _, trade in trades_df.iterrows():
        e_date = trade["Entry Date"]
        x_date = trade["Exit Date"]
        e_px   = trade["Entry Price"]

        mask = (df.index >= e_date) & (df.index <= x_date)
        segment = df.loc[mask, "Close"]

        for date, price in segment.items():
            equity[date] = capital * (float(price) / e_px)

        capital = equity[x_date] if not pd.isna(equity[x_date]) else capital

    # Forward-fill gaps (between trades, equity stays flat)
    equity = equity.ffill().fillna(1.0)
    return equity