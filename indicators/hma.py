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


def hma_signals(
    hma1: np.ndarray, hma2: np.ndarray, hma3: np.ndarray
) -> tuple[bool, str]:
    """
    Detect if latest bar has HMA1/HMA2 crossover and determine direction.
    Needs at least 2 bars of data.

    Returns:
        (cross, direction): cross=True if crossover occurred, direction='bull'/'bear'/''
    """
    if len(hma1) < 2:
        return False, ""

    prev_above = hma1[-2] > hma2[-2]
    curr_above = hma1[-1] > hma2[-1]

    if not prev_above and curr_above:
        # Bullish cross: HMA1 went from below to above HMA2
        if hma1[-1] > hma3[-1]:  # Trend filter: cloud is green
            return True, "bull"
        return True, ""  # Cross occurred but trend filter fails
    elif prev_above and not curr_above:
        # Bearish cross
        if hma1[-1] < hma3[-1]:  # Trend filter: cloud is red
            return True, "bear"
        return True, ""
    return False, ""
