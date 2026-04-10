import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from data_feed import get_ohlcv, MT5_TIMEFRAME_MAP


class TestGetOhlcv:
    def _make_mt5_rates(self, n=10):
        """Construct data in MT5 copy_rates_from_pos return format"""
        dtype = [
            ('time', '<i8'), ('open', '<f8'), ('high', '<f8'),
            ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'),
            ('spread', '<i4'), ('real_volume', '<i8')
        ]
        data = np.zeros(n, dtype=dtype)
        data['open']  = np.linspace(100, 110, n)
        data['high']  = data['open'] + 1
        data['low']   = data['open'] - 1
        data['close'] = data['open'] + 0.5
        data['time']  = np.arange(n) * 900  # 15min in seconds
        return data

    @patch('data_feed.mt5')
    def test_returns_dataframe(self, mock_mt5):
        mock_mt5.copy_rates_from_pos.return_value = self._make_mt5_rates(50)

        df = get_ohlcv("XAUUSD", "M15", bars=50)

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ['open', 'high', 'low', 'close']
        assert len(df) == 50
        assert df.index.tz is not None  # Must be timezone-aware UTC

    @patch('data_feed.mt5')
    def test_raises_on_none(self, mock_mt5):
        mock_mt5.copy_rates_from_pos.return_value = None

        with pytest.raises(RuntimeError, match="Failed to fetch"):
            get_ohlcv("XAUUSD", "M15", bars=50)

    def test_timeframe_map_contains_m15(self):
        assert "M15" in MT5_TIMEFRAME_MAP

    def test_timeframe_map_m15_value(self):
        assert MT5_TIMEFRAME_MAP["M15"] == 16390  # MT5 TIMEFRAME_M15 constant
