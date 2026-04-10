import numpy as np


def get_signal(
    hma1: np.ndarray,
    hma2: np.ndarray,
    hma3: np.ndarray,
    trend: np.ndarray,
) -> str:
    """
    Combine HMA and Blackflag signals to produce a trade direction.

    Entry conditions:
      BUY:  HMA1 crosses above HMA2 + HMA1 > HMA3 (green cloud) + Blackflag Trend==1
      SELL: HMA1 crosses below HMA2 + HMA1 < HMA3 (red cloud) + Blackflag Trend==-1

    Returns:
        "BUY" | "SELL" | "HOLD"
    """
    if len(hma1) < 2:
        return "HOLD"

    # Guard against NaN values during warmup period
    if any(np.isnan(v) for v in [hma1[-1], hma1[-2], hma2[-1], hma2[-2], hma3[-1]]):
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
