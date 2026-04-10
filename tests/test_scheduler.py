import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock, call
import sys

# Patch MetaTrader5 before importing scheduler
sys.modules.setdefault('MetaTrader5', MagicMock())

import scheduler


def _make_ohlcv(n=310):
    """Create a rising OHLCV DataFrame with enough bars for HMA(200) warmup."""
    close = np.linspace(2000, 2100, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame({
        'open':  close - 0.5,
        'high':  close + 1.0,
        'low':   close - 1.0,
        'close': close,
    }, index=idx)


CFG = {
    'timeframe': 'M15',
    'symbols': ['XAUUSD'],
    'indicators': {
        'hma':       {'length1': 50, 'length2': 100, 'length3': 200, 'source': 'close'},
        'blackflag': {'atr_period': 10, 'atr_factor': 3, 'trail_type': 'modified'},
    },
    'risk': {'risk_per_trade_pct': 1.0, 'rr_ratio': 2.0},
    'scheduler': {'warmup_bars': 300, 'poll_interval_seconds': 30},
    'mt5': {'login': 1, 'password': 'x', 'server': 'x'},
}


class TestRunOnce:
    @patch('scheduler.place_order')
    @patch('scheduler.get_symbol_info')
    @patch('scheduler.get_signal', return_value='HOLD')
    @patch('scheduler.get_ohlcv')
    def test_hold_signal_skips_order(self, mock_feed, mock_signal, mock_info, mock_order):
        mock_feed.return_value = _make_ohlcv(310)
        scheduler.run_once('XAUUSD', CFG)
        mock_order.assert_not_called()

    @patch('scheduler.place_order')
    @patch('scheduler.calculate_trade_params', return_value=(0.01, 1900.0, 2200.0))
    @patch('scheduler.get_symbol_info')
    @patch('scheduler.has_open_position', return_value=False)
    @patch('scheduler.mt5')
    @patch('scheduler.get_signal', return_value='BUY')
    @patch('scheduler.get_ohlcv')
    def test_buy_signal_places_order(self, mock_feed, mock_signal, mock_mt5,
                                     mock_pos, mock_info, mock_calc, mock_order):
        mock_feed.return_value = _make_ohlcv(310)
        tick = MagicMock()
        tick.ask = 2050.0
        mock_mt5.symbol_info_tick.return_value = tick
        account = MagicMock()
        account.balance = 10000.0
        mock_mt5.account_info.return_value = account

        scheduler.run_once('XAUUSD', CFG)
        mock_order.assert_called_once()

    @patch('scheduler.place_order')
    @patch('scheduler.get_symbol_info')
    @patch('scheduler.has_open_position', return_value=False)
    @patch('scheduler.mt5')
    @patch('scheduler.get_signal', return_value='BUY')
    @patch('scheduler.get_ohlcv')
    def test_none_tick_skips_order(self, mock_feed, mock_signal, mock_mt5, mock_pos, mock_info, mock_order):
        mock_feed.return_value = _make_ohlcv(310)
        mock_mt5.symbol_info_tick.return_value = None
        scheduler.run_once('XAUUSD', CFG)
        mock_order.assert_not_called()

    @patch('scheduler.place_order')
    @patch('scheduler.get_symbol_info')
    @patch('scheduler.has_open_position', return_value=False)
    @patch('scheduler.mt5')
    @patch('scheduler.get_signal', return_value='BUY')
    @patch('scheduler.get_ohlcv')
    def test_none_account_info_skips_order(self, mock_feed, mock_signal, mock_mt5, mock_pos, mock_info, mock_order):
        mock_feed.return_value = _make_ohlcv(310)
        tick = MagicMock()
        tick.ask = 2050.0
        mock_mt5.symbol_info_tick.return_value = tick
        mock_mt5.account_info.return_value = None
        scheduler.run_once('XAUUSD', CFG)
        mock_order.assert_not_called()
