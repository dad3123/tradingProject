import numpy as np
import pytest
from indicators.hma import wma, hma


class TestWma:
    def test_wma_simple(self):
        # WMA([1,2,3,4,5], period=3): weights=[1,2,3], last window=[3,4,5]
        # result = (3*1 + 4*2 + 5*3) / (1+2+3) = (3+8+15)/6 = 26/6 ≈ 4.333
        series = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = wma(series, 3)
        assert np.isnan(result[0])
        assert np.isnan(result[1])
        assert abs(result[4] - 26/6) < 1e-10

    def test_wma_period_1(self):
        series = np.array([1.0, 2.0, 3.0])
        result = wma(series, 1)
        np.testing.assert_array_almost_equal(result, [1.0, 2.0, 3.0])


class TestHma:
    def test_hma_length_4(self):
        series = np.linspace(100, 200, 50)  # linear uptrend
        result = hma(series, 4)
        assert not np.isnan(result[-1])
        assert 100 < result[-1] < 210

    def test_hma_returns_same_length(self):
        series = np.random.rand(100)
        result = hma(series, 10)
        assert len(result) == 100


