import numpy as np


def modified_true_range(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr_period: int,
) -> np.ndarray:
    """
    Blackflag modified true range (matches Pine Script modified trueRange).
    HiLo  = min(H-L, 1.5 * SMA(H-L, period))
    HRef  = H - C[1], or (H-C[1]) - 0.5*(L-H[1]) if L > H[1]
    LRef  = C[1] - L, or (C[1]-L) - 0.5*(L[1]-H) if H < L[1]
    trueRange = max(HiLo, HRef, LRef)
    """
    n = len(close)
    hl = high - low

    # SMA of H-L for HiLo upper bound
    hl_sma = np.full(n, np.nan)
    for i in range(atr_period - 1, n):
        hl_sma[i] = hl[i - atr_period + 1 : i + 1].mean()
    # Fill early bars to avoid nan propagation
    hl_sma[:atr_period - 1] = hl[:atr_period - 1]

    result = np.zeros(n)
    result[0] = hl[0]  # First bar has no previous, use HL

    for i in range(1, n):
        hilo = min(hl[i], 1.5 * hl_sma[i])

        if low[i] <= high[i - 1]:
            href = high[i] - close[i - 1]
        else:
            href = (high[i] - close[i - 1]) - 0.5 * (low[i] - high[i - 1])

        if high[i] >= low[i - 1]:
            lref = close[i - 1] - low[i]
        else:
            lref = (close[i - 1] - low[i]) - 0.5 * (low[i - 1] - high[i])

        result[i] = max(hilo, href, lref)

    return result


def wilder_ma(series: np.ndarray, period: int) -> np.ndarray:
    """
    Wilder smoothed MA (matches Pine Script Wild_ma function).
    wild[i] = wild[i-1] + (src[i] - wild[i-1]) / period
    Starts from 0 (matches Pine Script nz() behavior).
    """
    result = np.zeros(len(series))
    result[0] = series[0] / period   # nz() seed: wild[0] = 0 + (tr[0]-0)/period
    for i in range(1, len(series)):
        result[i] = result[i - 1] + (series[i] - result[i - 1]) / period
    return result


def _unmodified_true_range(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Standard true range: max(H-L, |H-C[1]|, |L-C[1]|)"""
    n = len(close)
    result = np.zeros(n)
    result[0] = high[0] - low[0]
    for i in range(1, n):
        result[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i]  - close[i - 1]),
        )
    return result


def blackflag(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr_period: int = 10,
    atr_factor: float = 3.0,
    trail_type: str = "modified",   # "modified" or "unmodified"
) -> tuple[np.ndarray, np.ndarray]:
    """
    Blackflag FTS trailing stop indicator.

    Returns:
        trend: np.ndarray, trend direction per bar: 1=uptrend, -1=downtrend
        trail: np.ndarray, trailing stop price per bar
    """
    n = len(close)
    if trail_type == "modified":
        tr = modified_true_range(high, low, close, atr_period)
    else:
        tr = _unmodified_true_range(high, low, close)
    wild = wilder_ma(tr, atr_period)

    trend_up   = np.zeros(n)
    trend_down = np.zeros(n)
    trend      = np.ones(n, dtype=int)

    loss = atr_factor * wild
    trend_up[0]   = close[0] - loss[0]
    trend_down[0] = close[0] + loss[0]

    for i in range(1, n):
        up = close[i] - loss[i]
        dn = close[i] + loss[i]

        trend_up[i]   = max(up, trend_up[i - 1])   if close[i - 1] > trend_up[i - 1]   else up
        trend_down[i] = min(dn, trend_down[i - 1]) if close[i - 1] < trend_down[i - 1] else dn

        if close[i] > trend_down[i - 1]:
            trend[i] = 1
        elif close[i] < trend_up[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]

    trail = np.where(trend == 1, trend_up, trend_down)
    return trend, trail
