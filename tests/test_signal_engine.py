import numpy as np
import pytest
from signal_engine import get_signal


class TestGetSignal:
    def _make_arrays(self, hma1_vals, hma2_vals, hma3_vals, trend_vals):
        return (
            np.array(hma1_vals, dtype=float),
            np.array(hma2_vals, dtype=float),
            np.array(hma3_vals, dtype=float),
            np.array(trend_vals, dtype=int),
        )

    def test_buy_signal(self):
        # HMA1 crosses above HMA2, HMA1 > HMA3, Blackflag uptrend
        hma1, hma2, hma3, trend = self._make_arrays(
            [99.0, 101.0],   # prev below, curr above hma2
            [100.0, 100.0],
            [95.0, 95.0],    # hma1 > hma3 ✓
            [1, 1],          # blackflag uptrend ✓
        )
        assert get_signal(hma1, hma2, hma3, trend) == "BUY"

    def test_sell_signal(self):
        # HMA1 crosses below HMA2, HMA1 < HMA3, Blackflag downtrend
        hma1, hma2, hma3, trend = self._make_arrays(
            [101.0, 99.0],
            [100.0, 100.0],
            [105.0, 105.0],  # hma1 < hma3 ✓
            [-1, -1],        # blackflag downtrend ✓
        )
        assert get_signal(hma1, hma2, hma3, trend) == "SELL"

    def test_hold_when_no_cross(self):
        # HMA1 always above HMA2, no crossover
        hma1, hma2, hma3, trend = self._make_arrays(
            [101.0, 102.0],
            [100.0, 100.0],
            [95.0, 95.0],
            [1, 1],
        )
        assert get_signal(hma1, hma2, hma3, trend) == "HOLD"

    def test_hold_when_cross_but_blackflag_disagrees(self):
        # HMA1 crosses above HMA2, but Blackflag is downtrend
        hma1, hma2, hma3, trend = self._make_arrays(
            [99.0, 101.0],
            [100.0, 100.0],
            [95.0, 95.0],
            [-1, -1],   # Blackflag downtrend — no confirmation
        )
        assert get_signal(hma1, hma2, hma3, trend) == "HOLD"

    def test_hold_when_cross_but_trend_filter_fails(self):
        # HMA1 crosses above HMA2, but HMA1 < HMA3 (ranging market filter)
        hma1, hma2, hma3, trend = self._make_arrays(
            [99.0, 101.0],
            [100.0, 100.0],
            [110.0, 110.0],  # hma1 < hma3 — trend filter fails
            [1, 1],
        )
        assert get_signal(hma1, hma2, hma3, trend) == "HOLD"

    def test_insufficient_data(self):
        hma1 = np.array([100.0])
        hma2 = np.array([100.0])
        hma3 = np.array([95.0])
        trend = np.array([1])
        assert get_signal(hma1, hma2, hma3, trend) == "HOLD"

    def test_hold_on_nan_values(self):
        import numpy as np
        # Simulate NaN warmup period — should not produce a signal
        hma1 = np.array([np.nan, 101.0])
        hma2 = np.array([np.nan, 100.0])
        hma3 = np.array([np.nan, 95.0])
        trend = np.array([1, 1])
        assert get_signal(hma1, hma2, hma3, trend) == "HOLD"
