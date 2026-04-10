"""
Verify Python-computed HMA and Blackflag values match TradingView chart.

Usage (requires Windows + MT5 installed):
  python scripts/verify_indicators.py

Output: Last 5 closed candle values for XAUUSD (15min).
Compare with TradingView Data Window (Ctrl+Shift+D).

TradingView indicator settings to match:
  HMA: Length1=50, Length2=100, Length3=200, Source=Close
  Blackflag FTS: Trail Type=modified, ATR Period=10, ATR Factor=3
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

try:
    import MetaTrader5 as mt5
except ImportError:
    print("ERROR: MetaTrader5 is not installed. Run this script on Windows.")
    sys.exit(1)

from data_feed import get_ohlcv
from indicators.hma import hma
from indicators.blackflag import blackflag


def main():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    mt5.initialize()
    mt5.login(
        login=cfg['mt5']['login'],
        password=cfg['mt5']['password'],
        server=cfg['mt5']['server'],
    )

    symbol = "XAUUSD"
    df = get_ohlcv(symbol, "M15", bars=500)
    df = df.iloc[:-1]  # Remove forming candle

    close = df['close'].values
    high  = df['high'].values
    low   = df['low'].values

    hma1 = hma(close, 50)
    hma2 = hma(close, 100)
    hma3 = hma(close, 200)
    trend, trail = blackflag(high, low, close, atr_period=10, atr_factor=3)

    print(f"\n{'='*65}")
    print(f"Last 5 closed candles — {symbol} 15min")
    print(f"Compare with TradingView Data Window (Ctrl+Shift+D)")
    print(f"{'='*65}")
    print(f"{'Time':<22} {'HMA1(50)':<12} {'HMA2(100)':<12} {'Trend':<8} {'Trail':<12}")
    print(f"{'-'*65}")
    for i in range(-5, 0):
        t = df.index[i].strftime('%Y-%m-%d %H:%M')
        print(f"{t:<22} {hma1[i]:<12.4f} {hma2[i]:<12.4f} {trend[i]:<8} {trail[i]:<12.4f}")

    print(f"\nAcceptable tolerance: <0.01% difference from TradingView values")
    print("If HMA values differ: check Source setting (must be 'close')")
    print("If Blackflag trail differs: ensure ATR Period=10, ATR Factor=3, Trail Type=modified")

    mt5.shutdown()


if __name__ == "__main__":
    main()
