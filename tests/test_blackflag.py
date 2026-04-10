import numpy as np
import pytest
from indicators.blackflag import modified_true_range, wilder_ma, blackflag


class TestModifiedTrueRange:
    def test_basic_calculation(self):
        high  = np.array([110.0, 112.0, 111.0])
        low   = np.array([108.0, 109.0, 107.0])
        close = np.array([109.0, 111.0, 110.0])
        atr_period = 3
        result = modified_true_range(high, low, close, atr_period)
        assert len(result) == 3
        assert all(r >= 0 for r in result)

    def test_non_negative(self):
        np.random.seed(42)
        n = 50
        close = np.cumsum(np.random.randn(n)) + 100
        high = close + np.abs(np.random.randn(n))
        low = close - np.abs(np.random.randn(n))
        result = modified_true_range(high, low, close, 10)
        assert np.all(result >= 0)


class TestWilderMa:
    def test_converges(self):
        # Wilder MA starts from 0, should converge to series mean
        series = np.full(200, 5.0)  # constant series
        result = wilder_ma(series, 10)
        # After enough bars, should be close to 5.0
        assert abs(result[-1] - 5.0) < 0.1

    def test_returns_same_length(self):
        series = np.random.rand(100)
        result = wilder_ma(series, 14)
        assert len(result) == 100


class TestBlackflag:
    def test_returns_trend_and_trail(self):
        np.random.seed(0)
        n = 200
        close = np.cumsum(np.random.randn(n) * 0.5) + 100
        high = close + np.abs(np.random.randn(n) * 0.3)
        low = close - np.abs(np.random.randn(n) * 0.3)
        trend, trail = blackflag(high, low, close, atr_period=10, atr_factor=3)
        assert len(trend) == n
        assert len(trail) == n
        # Trend should only be 1 or -1
        assert set(np.unique(trend)).issubset({1, -1})

    def test_trail_below_price_in_uptrend(self):
        # Continuously rising series, trailing stop should be below price
        close = np.linspace(100, 200, 300)
        high = close + 1
        low = close - 1
        trend, trail = blackflag(high, low, close, atr_period=10, atr_factor=3)
        # Last bars should be uptrend
        assert trend[-1] == 1
        assert trail[-1] < close[-1]

    def test_unmodified_trail_type(self):
        close = np.linspace(100, 200, 300)
        # Use narrow wicks so close-to-close gaps dominate, making the two
        # true-range formulas produce different values.
        high = close + 0.1
        low = close - 0.1
        trend_u, trail_u = blackflag(high, low, close, atr_period=10, atr_factor=3, trail_type="unmodified")
        trend_m, trail_m = blackflag(high, low, close, atr_period=10, atr_factor=3, trail_type="modified")
        # Both should produce valid uptrend results
        assert trend_u[-1] == 1
        assert trail_u[-1] < close[-1]
        # The two formulas produce different values
        assert not np.allclose(trail_u, trail_m)
