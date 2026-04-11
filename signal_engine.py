import numpy as np


def get_signal(
    hma1: np.ndarray,
    hma2: np.ndarray,
    hma3: np.ndarray,
    trend: np.ndarray,
    adx: np.ndarray | None = None,
    adx_threshold: float = 20.0,
) -> str:
    """
    Combine HMA, Blackflag and optional ADX signals to produce a trade direction.

    Entry conditions:
      BUY:  HMA1 crosses above HMA2 + HMA1 > HMA3 (green cloud) + Blackflag Trend==1
            + ADX[-1] >= adx_threshold (trending market, if adx array provided)
      SELL: HMA1 crosses below HMA2 + HMA1 < HMA3 (red cloud) + Blackflag Trend==-1
            + ADX[-1] >= adx_threshold (trending market, if adx array provided)

    Args:
        hma1, hma2, hma3: HMA arrays (at least 2 elements)
        trend:            Blackflag trend array (at least 2 elements)
        adx:              Optional ADX array aligned with hma arrays. When provided,
                          signals are suppressed unless ADX[-1] >= adx_threshold.
        adx_threshold:    Minimum ADX value to consider the market trending (default 20).

    Returns:
        "BUY" | "SELL" | "HOLD"
    """
    if len(hma1) < 2:
        return "HOLD"

    # Guard against NaN values during warmup period
    if any(np.isnan(v) for v in [hma1[-1], hma1[-2], hma2[-1], hma2[-2], hma3[-1]]):
        return "HOLD"

    # ADX trending-market filter: skip if ADX is not yet computed or below threshold
    if adx is not None:
        adx_val = adx[-1]
        if np.isnan(adx_val) or adx_val < adx_threshold:
            return "HOLD"

    prev_hma1_above_hma2 = hma1[-2] > hma2[-2]
    curr_hma1_above_hma2 = hma1[-1] > hma2[-1]
    curr_blackflag = trend[-1]

    bullish_cross = not prev_hma1_above_hma2 and curr_hma1_above_hma2
    bearish_cross = prev_hma1_above_hma2 and not curr_hma1_above_hma2

    trend_filter_bull = hma1[-1] > hma3[-1]   # HMA1 > HMA3: overall uptrend
    trend_filter_bear = hma1[-1] < hma3[-1]   # HMA1 < HMA3: overall downtrend

    if bullish_cross and trend_filter_bull and curr_blackflag == 1:
        return "BUY"
    if bearish_cross and trend_filter_bear and curr_blackflag == -1:
        return "SELL"
    return "HOLD"
