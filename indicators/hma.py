import math
import numpy as np


def wma(series: np.ndarray, period: int) -> np.ndarray:
    """Weighted Moving Average. Most recent bar gets weight=period, oldest gets weight=1."""
    weights = np.arange(1, period + 1, dtype=float)
    weight_sum = weights.sum()
    result = np.full(len(series), np.nan)
    for i in range(period - 1, len(series)):
        window = series[i - period + 1 : i + 1]
        result[i] = np.dot(window, weights) / weight_sum
    return result


def hma(series: np.ndarray, period: int) -> np.ndarray:
    """Hull Moving Average: WMA(2*WMA(n/2) - WMA(n), sqrt(n))"""
    half = period // 2
    sqrt_period = round(math.sqrt(period))
    wma_half = wma(series, half)
    wma_full = wma(series, period)
    diff = 2 * wma_half - wma_full
    return wma(diff, sqrt_period)
