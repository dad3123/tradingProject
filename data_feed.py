import pandas as pd
import numpy as np

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # Allow import without MT5 (tests mock it)

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
        RuntimeError: When MT5 returns None
    """
    tf = MT5_TIMEFRAME_MAP[timeframe]
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)

    if rates is None:
        raise RuntimeError(f"Failed to fetch OHLCV for {symbol} {timeframe}")

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time', inplace=True)
    df = df[['open', 'high', 'low', 'close']]
    return df
