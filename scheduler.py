import time
import logging

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
from executor import place_order, get_symbol_info, has_open_position

logger = logging.getLogger(__name__)


def _reconnect_mt5(cfg: dict) -> bool:
    """Attempt to reconnect to MT5. Returns True on success."""
    try:
        if mt5 is None:
            return False
        mt5.shutdown()
        if not mt5.initialize():
            return False
        if not mt5.login(
            login=cfg['mt5']['login'],
            password=cfg['mt5']['password'],
            server=cfg['mt5']['server'],
        ):
            return False
        logger.info("MT5 reconnected successfully")
        return True
    except Exception as e:
        logger.error(f"MT5 reconnect failed: {e}")
        return False


def run_once(symbol: str, cfg: dict) -> None:
    """
    Fetch latest data, compute indicators, check signal, place order.
    Called once per 15min candle close.
    """
    if mt5 is None:
        raise RuntimeError("MetaTrader5 is not installed; cannot run scheduler")
    warmup = cfg['scheduler']['warmup_bars']
    hma_cfg = cfg['indicators']['hma']
    bf_cfg  = cfg['indicators']['blackflag']
    risk_cfg = cfg['risk']

    # 1. Fetch data — pull one extra bar, drop the forming (last) candle
    df = get_ohlcv(symbol, cfg['timeframe'], bars=warmup + 1)
    df = df.iloc[:-1]  # only use closed candles

    source_col = hma_cfg.get('source', 'close')
    close = df[source_col].values   # HMA source (configurable: close/open/high/low)
    high  = df['high'].values
    low   = df['low'].values

    # 2. Compute indicators
    hma1 = hma(close, hma_cfg['length1'])
    hma2 = hma(close, hma_cfg['length2'])
    hma3 = hma(close, hma_cfg['length3'])
    trend, trail = blackflag(high, low, close,
                             atr_period=bf_cfg['atr_period'],
                             atr_factor=bf_cfg['atr_factor'],
                             trail_type=bf_cfg.get('trail_type', 'modified'))

    # 3. Get signal
    signal = get_signal(hma1, hma2, hma3, trend)
    logger.info(f"[{symbol}] Signal: {signal}, HMA1={hma1[-1]:.4f}, "
                f"Trend={trend[-1]}, Trail={trail[-1]:.4f}")

    if signal == "HOLD":
        return

    # Early check: skip expensive API calls if position already exists
    if has_open_position(symbol):
        logger.info(f"[{symbol}] Position already open, skipping.")
        return

    # 4. Calculate risk parameters
    symbol_info = get_symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error(f"[{symbol}] Cannot get tick price, skipping")
        return
    entry_price = tick.ask if signal == "BUY" else tick.bid
    account_info = mt5.account_info()
    if account_info is None:
        logger.error(f"[{symbol}] Cannot get account info, skipping")
        return
    account_balance = account_info.balance
    lots, sl, tp = calculate_trade_params(
        signal=signal,
        entry_price=entry_price,
        trail=trail[-1],
        account_balance=account_balance,
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
                # Attempt reconnect if it looks like a connection error
                if isinstance(e, RuntimeError):
                    logger.info("Attempting MT5 reconnect...")
                    _reconnect_mt5(cfg)

        time.sleep(interval)
