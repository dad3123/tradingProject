from datetime import datetime

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # Allow import without MT5 (tests mock it)

if mt5 is not None:
    MT5_TIMEFRAME_MAP = {
        "M1":  mt5.TIMEFRAME_M1,
        "M5":  mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1":  mt5.TIMEFRAME_H1,
        "H4":  mt5.TIMEFRAME_H4,
        "D1":  mt5.TIMEFRAME_D1,
    }
else:
    MT5_TIMEFRAME_MAP = {
        "M1":  16385,
        "M5":  16388,
        "M15": 16390,
        "M30": 16392,
        "H1":  16408,
        "H4":  16416,
        "D1":  16424,
    }


def get_ohlcv(symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
    """
    Fetch historical OHLCV data from MT5.

    Args:
        symbol:    Symbol code e.g. "XAUUSD"
        timeframe: Timeframe string e.g. "M15"
        bars:      Number of bars to fetch

    Returns:
        DataFrame with columns ['open', 'high', 'low', 'close'],
        index is datetime (UTC), ascending order, newest bar is last row.

    Raises:
        RuntimeError: When MT5 is not installed or returns None
    """
    if mt5 is None:
        raise RuntimeError("MetaTrader5 is not installed; cannot call get_ohlcv")
    tf = MT5_TIMEFRAME_MAP[timeframe]
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)

    if rates is None:
        raise RuntimeError(f"Failed to fetch OHLCV for {symbol} {timeframe}")

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time', inplace=True)
    df = df[['open', 'high', 'low', 'close']]
    return df


def get_ohlcv_range(
    symbol: str,
    timeframe: str,
    date_from: datetime,
    date_to: datetime,
) -> pd.DataFrame:
    """
    Fetch historical OHLCV data from MT5 for a specific date range.

    Args:
        symbol:    Symbol code e.g. "XAUUSD"
        timeframe: Timeframe string e.g. "M15"
        date_from: Start datetime (UTC, inclusive)
        date_to:   End datetime (UTC, inclusive)

    Returns:
        DataFrame with columns ['open', 'high', 'low', 'close'],
        index is datetime (UTC), ascending order, newest bar is last row.

    Raises:
        RuntimeError: When MT5 is not installed or returns None
    """
    if mt5 is None:
        raise RuntimeError("MetaTrader5 is not installed; cannot call get_ohlcv_range")
    tf = MT5_TIMEFRAME_MAP[timeframe]
    rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)

    if rates is None:
        raise RuntimeError(f"Failed to fetch OHLCV range for {symbol} {timeframe}")

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time', inplace=True)
    df = df[['open', 'high', 'low', 'close']]
    return df
