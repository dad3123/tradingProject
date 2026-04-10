import time
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from data_feed import get_ohlcv
from indicators.hma import hma
from indicators.blackflag import blackflag
from signal_engine import get_signal
from risk_manager import calculate_trade_params
from executor import place_order, get_symbol_info

logger = logging.getLogger(__name__)


def run_once(symbol: str, cfg: dict) -> None:
    """
    Fetch latest data, compute indicators, check signal, place order.
    Called once per 15min candle close.
    """
    warmup = cfg['scheduler']['warmup_bars']
    hma_cfg = cfg['indicators']['hma']
    bf_cfg  = cfg['indicators']['blackflag']
    risk_cfg = cfg['risk']

    # 1. Fetch data — pull one extra bar, drop the forming (last) candle
    df = get_ohlcv(symbol, cfg['timeframe'], bars=warmup + 1)
    df = df.iloc[:-1]  # only use closed candles

    close = df['close'].values
    high  = df['high'].values
    low   = df['low'].values

    # 2. Compute indicators
    hma1 = hma(close, hma_cfg['length1'])
    hma2 = hma(close, hma_cfg['length2'])
    hma3 = hma(close, hma_cfg['length3'])
    trend, trail = blackflag(high, low, close,
                             atr_period=bf_cfg['atr_period'],
                             atr_factor=bf_cfg['atr_factor'])

    # 3. Get signal
    signal = get_signal(hma1, hma2, hma3, trend)
    logger.info(f"[{symbol}] Signal: {signal}, HMA1={hma1[-1]:.4f}, "
                f"Trend={trend[-1]}, Trail={trail[-1]:.4f}")

    if signal == "HOLD":
        return

    # 4. Calculate risk parameters
    symbol_info = get_symbol_info(symbol)
    entry_price = close[-1]
    lots, sl, tp = calculate_trade_params(
        signal=signal,
        entry_price=entry_price,
        trail=trail[-1],
        account_balance=mt5.account_info().balance,
        risk_pct=risk_cfg['risk_per_trade_pct'],
        rr_ratio=risk_cfg['rr_ratio'],
        symbol_info=symbol_info,
    )

    # 5. Place order
    place_order(symbol, signal, lots, sl, tp)


def start(cfg: dict) -> None:
    """
    Main loop: poll every poll_interval_seconds, detect new closed candle,
    run run_once() for each symbol.
    """
    symbols = cfg['symbols']
    interval = cfg['scheduler']['poll_interval_seconds']
    last_bar_time: dict[str, pd.Timestamp | None] = {s: None for s in symbols}

    logger.info("Scheduler started. Watching: %s", symbols)

    while True:
        for symbol in symbols:
            try:
                df = get_ohlcv(symbol, cfg['timeframe'], bars=2)
                # index[-1] is forming candle, index[-2] is latest closed candle
                latest_closed_time = df.index[-2]

                if last_bar_time[symbol] != latest_closed_time:
                    last_bar_time[symbol] = latest_closed_time
                    logger.info(f"[{symbol}] New candle closed at {latest_closed_time}")
                    run_once(symbol, cfg)
            except Exception as e:
                logger.exception(f"[{symbol}] Error during run: {e}")

        time.sleep(interval)
