"""
Backtest script: simulate HMA + Blackflag strategy on 6 months MT5 historical data.

Usage (requires Windows + MT5):
  python scripts/backtest.py
Output: backtest_results.txt in project root.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import yaml

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from data_feed import get_ohlcv
from indicators.hma import hma
from indicators.blackflag import blackflag
from signal_engine import get_signal
from risk_manager import SymbolInfo, calculate_trade_params
from executor import get_symbol_info


# 最近6个月 15min K线根数（约17280根）
SIX_MONTHS_BARS = 17_280


@dataclass
class Trade:
    symbol: str
    direction: str          # "BUY" or "SELL"
    entry_time: Any
    entry_price: float
    lots: float
    sl: float
    tp: float
    entry_bar: int          # internal: bar index in df
    exit_time: Any = None
    exit_price: float = None
    exit_reason: str = None  # "止盈" | "止损" | "持仓中"
    pnl_points: float = None
    pnl_usd: float = None


def _simulate_trades(
    df: pd.DataFrame,
    signals: list,
    trail_arr: np.ndarray,
    warmup: int,
    cfg: dict,
    symbol_info: SymbolInfo,
    account_balance: float,
    symbol: str,
) -> list:
    """
    Core simulation loop. Processes bars from warmup onward.
    Does NOT call MT5 — fully testable with synthetic data.

    Exit priority (when both SL and TP hit in same bar): SL first (pessimistic).
    No re-entry on the bar an existing trade exits.
    """
    risk_cfg = cfg['risk']
    trades = []
    current_trade = None  # type: Trade | None

    for i in range(warmup, len(df)):
        bar = df.iloc[i]
        just_exited = False

        # ── 1. Check exit for current open trade ──────────────────────────
        if current_trade is not None and i > current_trade.entry_bar:
            if current_trade.direction == "BUY":
                if bar['low'] <= current_trade.sl:
                    _close_trade(current_trade, df.index[i], current_trade.sl, "止损", symbol_info)
                    trades.append(current_trade)
                    current_trade = None
                    just_exited = True
                elif bar['high'] >= current_trade.tp:
                    _close_trade(current_trade, df.index[i], current_trade.tp, "止盈", symbol_info)
                    trades.append(current_trade)
                    current_trade = None
                    just_exited = True
            else:  # SELL
                if bar['high'] >= current_trade.sl:
                    _close_trade(current_trade, df.index[i], current_trade.sl, "止损", symbol_info)
                    trades.append(current_trade)
                    current_trade = None
                    just_exited = True
                elif bar['low'] <= current_trade.tp:
                    _close_trade(current_trade, df.index[i], current_trade.tp, "止盈", symbol_info)
                    trades.append(current_trade)
                    current_trade = None
                    just_exited = True

        # ── 2. Check entry signal (skip bar where we just exited) ─────────
        if current_trade is None and not just_exited and signals[i] != "HOLD":
            entry_price = float(df['close'].iloc[i])
            trail_val = float(trail_arr[i])
            try:
                lots, sl, tp = calculate_trade_params(
                    signal=signals[i],
                    entry_price=entry_price,
                    trail=trail_val,
                    account_balance=account_balance,
                    risk_pct=risk_cfg['risk_per_trade_pct'],
                    rr_ratio=risk_cfg['rr_ratio'],
                    symbol_info=symbol_info,
                )
            except ValueError:
                continue  # invalid SL (trail too close to price), skip

            current_trade = Trade(
                symbol=symbol,
                direction=signals[i],
                entry_time=df.index[i],
                entry_price=entry_price,
                lots=lots,
                sl=sl,
                tp=tp,
                entry_bar=i,
            )

    # ── 3. Handle position still open at end of data ──────────────────────
    if current_trade is not None:
        current_trade.exit_reason = "持仓中"
        trades.append(current_trade)

    return trades


def _close_trade(trade: Trade, exit_time, exit_price: float, reason: str, symbol_info: SymbolInfo) -> None:
    """Mutate trade in-place with exit info and pnl calculation."""
    trade.exit_time = exit_time
    trade.exit_price = exit_price
    trade.exit_reason = reason

    if trade.direction == "BUY":
        trade.pnl_points = exit_price - trade.entry_price
    else:
        trade.pnl_points = trade.entry_price - exit_price

    trade.pnl_usd = (trade.pnl_points / symbol_info.trade_tick_size) * symbol_info.trade_tick_value * trade.lots
