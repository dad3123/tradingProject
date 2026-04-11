import numpy as np


def adx(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """
    Average Directional Index (ADX) using Wilder smoothing.

    ADX measures trend *strength* (not direction): values above 20-25 indicate
    a trending market, below 20 indicates a ranging/choppy market.

    Returns:
        adx_arr: np.ndarray, ADX value per bar (NaN during warmup).
    """
    n = len(close)
    if n < period + 1:
        return np.full(n, np.nan)

    # ── True Range ────────────────────────────────────────────────────────
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i]  - close[i - 1]),
        )

    # ── Directional Movement ──────────────────────────────────────────────
    plus_dm  = np.zeros(n)
    minus_dm = np.zeros(n)
    for i in range(1, n):
        up   = high[i]  - high[i - 1]
        down = low[i - 1] - low[i]
        if up > down and up > 0:
            plus_dm[i] = up
        if down > up and down > 0:
            minus_dm[i] = down

    # ── Wilder Smoothing ──────────────────────────────────────────────────
    def _wilder_smooth(arr: np.ndarray) -> np.ndarray:
        """Wilder smoothed moving average, initialised from the first `period` sum."""
        result = np.zeros(n)
        result[period - 1] = arr[:period].sum()
        for i in range(period, n):
            result[i] = result[i - 1] - result[i - 1] / period + arr[i]
        return result

    smooth_tr       = _wilder_smooth(tr)
    smooth_plus_dm  = _wilder_smooth(plus_dm)
    smooth_minus_dm = _wilder_smooth(minus_dm)

    # ── DI lines ─────────────────────────────────────────────────────────
    plus_di  = np.where(smooth_tr > 0, 100.0 * smooth_plus_dm  / smooth_tr, 0.0)
    minus_di = np.where(smooth_tr > 0, 100.0 * smooth_minus_dm / smooth_tr, 0.0)

    # ── DX → ADX ─────────────────────────────────────────────────────────
    di_sum  = plus_di + minus_di
    dx = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0.0)

    adx_arr = np.full(n, np.nan)
    # First valid ADX: average of first `period` DX values (starting from period-1)
    start = 2 * period - 2          # first bar where both smoothing and DX are ready
    if start >= n:
        return adx_arr
    adx_arr[start] = dx[period - 1 : 2 * period - 1].mean()
    for i in range(start + 1, n):
        adx_arr[i] = (adx_arr[i - 1] * (period - 1) + dx[i]) / period

    return adx_arr
