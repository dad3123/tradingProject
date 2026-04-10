# MT5 自动交易系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个基于 HMA + Blackflag FTS 指标信号、通过 MT5 API 自动交易 BTCUSD 和 XAUUSD 的 Python 程序。

**Architecture:** 从 MT5 拉取 15min OHLCV 数据 → 本地计算 HMA(50/100/200) 和 Blackflag ATR 追踪止损 → 合并信号 → 计算仓位/SL/TP → MT5 下单。每根 15min K 线收盘时触发一次检测，防止重复开仓。

**Tech Stack:** Python 3.10+, MetaTrader5, pandas, numpy, pyyaml, schedule, pytest

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `requirements.txt` | 依赖声明 |
| `config.yaml` | 所有可配置参数（MT5账户、品种、指标参数、风险设置） |
| `data_feed.py` | 通过 MT5 API 拉取 OHLCV 历史数据，返回 DataFrame |
| `indicators/hma.py` | WMA 和 HMA 计算函数，返回 numpy 数组 |
| `indicators/blackflag.py` | 修正 ATR + Wilder 均线 + 追踪止损，返回 Trend 和 trail 数组 |
| `signal_engine.py` | 接收指标数组，输出 BUY/SELL/HOLD 信号 |
| `risk_manager.py` | 计算手数、SL 价格、TP 价格 |
| `executor.py` | MT5 下单、查询持仓、防重复开仓 |
| `scheduler.py` | 每 30 秒检测新 K 线收盘，触发完整交易流程 |
| `main.py` | 入口：初始化 MT5、加载配置、启动调度器 |
| `tests/test_hma.py` | HMA 计算单元测试 |
| `tests/test_blackflag.py` | Blackflag 计算单元测试 |
| `tests/test_signal_engine.py` | 信号合并逻辑单元测试 |
| `tests/test_risk_manager.py` | 仓位和 SL/TP 计算单元测试 |
| `tests/test_executor.py` | MT5 下单逻辑单元测试（mock MT5） |

---

## Task 1: 项目初始化

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `indicators/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: 创建 requirements.txt**

```
MetaTrader5>=5.0.45
pandas>=2.0.0
numpy>=1.26.0
pyyaml>=6.0
schedule>=1.2.0
pytest>=8.0.0
```

- [ ] **Step 2: 创建 config.yaml**

```yaml
mt5:
  login: 12345678          # 替换为你的账号
  password: "your_password" # 替换为你的密码
  server: "ICMarkets-Demo"  # 替换为你的经纪商服务器

symbols:
  - BTCUSD
  - XAUUSD

timeframe: M15             # 15分钟

indicators:
  hma:
    length1: 50
    length2: 100
    length3: 200
    source: close
  blackflag:
    trail_type: modified
    atr_period: 10
    atr_factor: 3

risk:
  risk_per_trade_pct: 1.0  # 每单风险占账户余额的百分比
  rr_ratio: 2.0            # 止盈/止损比例

scheduler:
  poll_interval_seconds: 30  # 每隔多少秒检查一次新K线
  warmup_bars: 300           # 启动时拉取多少根历史K线用于指标计算
```

- [ ] **Step 3: 创建空的 __init__.py 文件**

```bash
touch indicators/__init__.py tests/__init__.py
```

- [ ] **Step 4: 安装依赖**

```bash
pip install -r requirements.txt
```

Expected: 所有包安装成功，无报错。

- [ ] **Step 5: 提交**

```bash
git init
git add requirements.txt config.yaml indicators/__init__.py tests/__init__.py
git commit -m "feat: project scaffold with config and dependencies"
```

---

## Task 2: HMA 指标计算

**Files:**
- Create: `indicators/hma.py`
- Create: `tests/test_hma.py`

Pine Script 原始公式：
```
hullma = wma(2*wma(src, length/2) - wma(src, length), round(sqrt(length)))
```

- [ ] **Step 1: 写失败测试**

创建 `tests/test_hma.py`：

```python
import numpy as np
import pytest
from indicators.hma import wma, hma, hma_signals


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
        # 用足够长的序列确保结果不是 nan
        series = np.linspace(100, 200, 50)  # 线性上升
        result = hma(series, 4)
        # 线性序列，HMA 应接近价格本身
        assert not np.isnan(result[-1])
        assert 100 < result[-1] < 210

    def test_hma_returns_same_length(self):
        series = np.random.rand(100)
        result = hma(series, 10)
        assert len(result) == 100


class TestHmaSignals:
    def test_bullish_cross(self):
        # 构造 hma1[-2] < hma2[-2]，hma1[-1] > hma2[-1] 的场景
        hma1 = np.array([99.0, 101.0])  # 从低于到高于 hma2
        hma2 = np.array([100.0, 100.0])
        hma3 = np.array([95.0, 95.0])   # hma1 > hma3，趋势过滤通过
        cross, direction = hma_signals(hma1, hma2, hma3)
        assert cross is True
        assert direction == "bull"

    def test_bearish_cross(self):
        hma1 = np.array([101.0, 99.0])
        hma2 = np.array([100.0, 100.0])
        hma3 = np.array([105.0, 105.0])  # hma1 < hma3
        cross, direction = hma_signals(hma1, hma2, hma3)
        assert cross is True
        assert direction == "bear"

    def test_no_cross(self):
        hma1 = np.array([101.0, 102.0])
        hma2 = np.array([100.0, 100.0])
        hma3 = np.array([95.0, 95.0])
        cross, direction = hma_signals(hma1, hma2, hma3)
        assert cross is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_hma.py -v
```

Expected: `ImportError: No module named 'indicators.hma'`

- [ ] **Step 3: 实现 indicators/hma.py**

```python
import math
import numpy as np


def wma(series: np.ndarray, period: int) -> np.ndarray:
    """Weighted Moving Average. 最近一根权重最大（=period），最早一根权重为 1。"""
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
    检测最新K线是否发生 HMA1/HMA2 交叉，并判断方向。
    需要至少 2 根 K 线数据（当前 + 前一根）。

    Returns:
        (cross, direction): cross=True 表示发生穿越，direction='bull'/'bear'/''
    """
    if len(hma1) < 2:
        return False, ""

    prev_above = hma1[-2] > hma2[-2]
    curr_above = hma1[-1] > hma2[-1]

    if not prev_above and curr_above:
        # 上穿：HMA1 从低于 HMA2 变为高于 HMA2
        if hma1[-1] > hma3[-1]:  # 趋势过滤：云朵为绿
            return True, "bull"
        return True, ""  # 穿越但趋势过滤不通过
    elif prev_above and not curr_above:
        # 下穿
        if hma1[-1] < hma3[-1]:  # 趋势过滤：云朵为红
            return True, "bear"
        return True, ""
    return False, ""
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_hma.py -v
```

Expected: 所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add indicators/hma.py tests/test_hma.py
git commit -m "feat: add HMA indicator (WMA, HMA, crossover detection)"
```

---

## Task 3: Blackflag FTS 指标计算

**Files:**
- Create: `indicators/blackflag.py`
- Create: `tests/test_blackflag.py`

Pine Script 原始逻辑：修正真实波幅 → Wilder 均线 → 追踪止损 → 趋势方向

- [ ] **Step 1: 写失败测试**

创建 `tests/test_blackflag.py`：

```python
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
        # Wilder MA 从 0 开始，应逐渐收敛到序列均值附近
        series = np.full(200, 5.0)  # 常数序列
        result = wilder_ma(series, 10)
        # 经过足够多的 bar 后，应接近 5.0
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
        # Trend 只应该是 1 或 -1
        assert set(np.unique(trend)).issubset({1, -1})

    def test_trail_below_price_in_uptrend(self):
        # 持续上涨序列，追踪止损应在价格下方
        close = np.linspace(100, 200, 300)
        high = close + 1
        low = close - 1
        trend, trail = blackflag(high, low, close, atr_period=10, atr_factor=3)
        # 最后几根K线应该是上升趋势
        assert trend[-1] == 1
        assert trail[-1] < close[-1]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_blackflag.py -v
```

Expected: `ImportError: No module named 'indicators.blackflag'`

- [ ] **Step 3: 实现 indicators/blackflag.py**

```python
import numpy as np


def modified_true_range(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr_period: int,
) -> np.ndarray:
    """
    Blackflag 修正真实波幅（对应 Pine Script 的 modified trueRange）。
    HiLo  = min(H-L, 1.5 * SMA(H-L, period))
    HRef  = H - C[1]，若 L <= H[1]，否则 (H-C[1]) - 0.5*(L-H[1])
    LRef  = C[1] - L，若 H >= L[1]，否则 (C[1]-L) - 0.5*(L[1]-H)
    trueRange = max(HiLo, HRef, LRef)
    """
    n = len(close)
    hl = high - low

    # SMA of H-L，用于 HiLo 的上限
    hl_sma = np.full(n, np.nan)
    for i in range(atr_period - 1, n):
        hl_sma[i] = hl[i - atr_period + 1 : i + 1].mean()
    # 第一根K线前 SMA 用 hl 本身替代（避免 nan 传播）
    hl_sma[:atr_period - 1] = hl[:atr_period - 1]

    result = np.zeros(n)
    result[0] = hl[0]  # 第一根没有前一根，用 HL 代替

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
    Wilder 平滑均线（对应 Pine Script Wild_ma 函数）。
    wild[i] = wild[i-1] + (src[i] - wild[i-1]) / period
    初始值从 0 开始（与 Pine Script nz() 行为一致）。
    """
    result = np.zeros(len(series))
    for i in range(len(series)):
        result[i] = result[i - 1] + (series[i] - result[i - 1]) / period
    return result


def blackflag(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr_period: int = 10,
    atr_factor: float = 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Blackflag FTS 追踪止损指标。

    Returns:
        trend: np.ndarray，每根K线的趋势方向，1=上涨，-1=下跌
        trail: np.ndarray，每根K线的追踪止损价格
    """
    n = len(close)
    tr = modified_true_range(high, low, close, atr_period)
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_blackflag.py -v
```

Expected: 所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add indicators/blackflag.py tests/test_blackflag.py
git commit -m "feat: add Blackflag FTS indicator (modified ATR trailing stop)"
```

---

## Task 4: Signal Engine（信号合并）

**Files:**
- Create: `signal_engine.py`
- Create: `tests/test_signal_engine.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_signal_engine.py`：

```python
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
        # HMA1 上穿 HMA2，HMA1 > HMA3，Blackflag 上涨
        hma1, hma2, hma3, trend = self._make_arrays(
            [99.0, 101.0],   # 前一根低于，当前高于 hma2
            [100.0, 100.0],
            [95.0, 95.0],    # hma1 > hma3 ✓
            [1, 1],          # blackflag 上涨 ✓
        )
        assert get_signal(hma1, hma2, hma3, trend) == "BUY"

    def test_sell_signal(self):
        # HMA1 下穿 HMA2，HMA1 < HMA3，Blackflag 下跌
        hma1, hma2, hma3, trend = self._make_arrays(
            [101.0, 99.0],
            [100.0, 100.0],
            [105.0, 105.0],  # hma1 < hma3 ✓
            [-1, -1],        # blackflag 下跌 ✓
        )
        assert get_signal(hma1, hma2, hma3, trend) == "SELL"

    def test_hold_when_no_cross(self):
        # HMA1 始终高于 HMA2，无穿越
        hma1, hma2, hma3, trend = self._make_arrays(
            [101.0, 102.0],
            [100.0, 100.0],
            [95.0, 95.0],
            [1, 1],
        )
        assert get_signal(hma1, hma2, hma3, trend) == "HOLD"

    def test_hold_when_cross_but_blackflag_disagrees(self):
        # HMA1 上穿 HMA2，但 Blackflag 是下跌趋势
        hma1, hma2, hma3, trend = self._make_arrays(
            [99.0, 101.0],
            [100.0, 100.0],
            [95.0, 95.0],
            [-1, -1],   # Blackflag 下跌，不确认
        )
        assert get_signal(hma1, hma2, hma3, trend) == "HOLD"

    def test_hold_when_cross_but_trend_filter_fails(self):
        # HMA1 上穿 HMA2，但 HMA1 < HMA3（震荡过滤触发）
        hma1, hma2, hma3, trend = self._make_arrays(
            [99.0, 101.0],
            [100.0, 100.0],
            [110.0, 110.0],  # hma1 < hma3，趋势过滤不通过
            [1, 1],
        )
        assert get_signal(hma1, hma2, hma3, trend) == "HOLD"

    def test_insufficient_data(self):
        hma1 = np.array([100.0])
        hma2 = np.array([100.0])
        hma3 = np.array([95.0])
        trend = np.array([1])
        assert get_signal(hma1, hma2, hma3, trend) == "HOLD"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_signal_engine.py -v
```

Expected: `ImportError: No module named 'signal_engine'`

- [ ] **Step 3: 实现 signal_engine.py**

```python
import numpy as np


def get_signal(
    hma1: np.ndarray,
    hma2: np.ndarray,
    hma3: np.ndarray,
    trend: np.ndarray,
) -> str:
    """
    合并 HMA 和 Blackflag 信号，输出交易方向。

    入场条件：
      BUY:  HMA1 上穿 HMA2 + HMA1 > HMA3（云朵绿）+ Blackflag Trend==1
      SELL: HMA1 下穿 HMA2 + HMA1 < HMA3（云朵红）+ Blackflag Trend==-1

    Returns:
        "BUY" | "SELL" | "HOLD"
    """
    if len(hma1) < 2:
        return "HOLD"

    prev_hma1_above_hma2 = hma1[-2] > hma2[-2]
    curr_hma1_above_hma2 = hma1[-1] > hma2[-1]
    curr_blackflag = trend[-1]

    bullish_cross = not prev_hma1_above_hma2 and curr_hma1_above_hma2
    bearish_cross = prev_hma1_above_hma2 and not curr_hma1_above_hma2

    trend_filter_bull = hma1[-1] > hma3[-1]   # HMA1 > HMA3，整体上升
    trend_filter_bear = hma1[-1] < hma3[-1]   # HMA1 < HMA3，整体下降

    if bullish_cross and trend_filter_bull and curr_blackflag == 1:
        return "BUY"
    if bearish_cross and trend_filter_bear and curr_blackflag == -1:
        return "SELL"
    return "HOLD"
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_signal_engine.py -v
```

Expected: 所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add signal_engine.py tests/test_signal_engine.py
git commit -m "feat: add signal engine combining HMA and Blackflag signals"
```

---

## Task 5: Risk Manager（风险管理）

**Files:**
- Create: `risk_manager.py`
- Create: `tests/test_risk_manager.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_risk_manager.py`：

```python
import pytest
from risk_manager import calculate_trade_params, SymbolInfo


class TestCalculateTradeParams:
    def _symbol_info(self):
        return SymbolInfo(
            trade_tick_value=1.0,   # 每个 tick 价值 1 USD
            trade_tick_size=0.01,   # 最小价格变动
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )

    def test_buy_params(self):
        # 账户 10000，风险 1%，SL距离=100点
        # risk_amount = 100 USD
        # sl_ticks = 100 / 0.01 = 10000
        # lots = 100 / (10000 * 1.0) = 0.01
        info = self._symbol_info()
        lots, sl, tp = calculate_trade_params(
            signal="BUY",
            entry_price=2000.0,
            trail=1900.0,        # SL 在入场价下方 100
            account_balance=10000.0,
            risk_pct=1.0,
            rr_ratio=2.0,
            symbol_info=info,
        )
        assert abs(lots - 0.01) < 1e-9
        assert abs(sl - 1900.0) < 1e-9
        assert abs(tp - 2200.0) < 1e-9  # entry + 100*2

    def test_sell_params(self):
        info = self._symbol_info()
        lots, sl, tp = calculate_trade_params(
            signal="SELL",
            entry_price=2000.0,
            trail=2100.0,        # SL 在入场价上方 100
            account_balance=10000.0,
            risk_pct=1.0,
            rr_ratio=2.0,
            symbol_info=info,
        )
        assert abs(lots - 0.01) < 1e-9
        assert abs(sl - 2100.0) < 1e-9
        assert abs(tp - 1800.0) < 1e-9  # entry - 100*2

    def test_lots_clamped_to_min(self):
        # 当计算出的手数小于 volume_min 时，应使用 volume_min
        info = self._symbol_info()
        lots, sl, tp = calculate_trade_params(
            signal="BUY",
            entry_price=2000.0,
            trail=1000.0,        # SL距离很大=1000，手数会非常小
            account_balance=100.0,
            risk_pct=1.0,
            rr_ratio=2.0,
            symbol_info=info,
        )
        assert lots >= info.volume_min

    def test_lots_clamped_to_max(self):
        info = self._symbol_info()
        lots, sl, tp = calculate_trade_params(
            signal="BUY",
            entry_price=2000.0,
            trail=1999.99,       # SL距离极小，手数会极大
            account_balance=1_000_000.0,
            risk_pct=10.0,
            rr_ratio=2.0,
            symbol_info=info,
        )
        assert lots <= info.volume_max
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_risk_manager.py -v
```

Expected: `ImportError: No module named 'risk_manager'`

- [ ] **Step 3: 实现 risk_manager.py**

```python
from dataclasses import dataclass


@dataclass
class SymbolInfo:
    trade_tick_value: float   # 每个 tick 的货币价值（账户货币）
    trade_tick_size: float    # 最小价格变动单位
    volume_min: float         # 最小手数
    volume_max: float         # 最大手数
    volume_step: float        # 手数步长


def calculate_trade_params(
    signal: str,
    entry_price: float,
    trail: float,
    account_balance: float,
    risk_pct: float,
    rr_ratio: float,
    symbol_info: SymbolInfo,
) -> tuple[float, float, float]:
    """
    计算开仓手数、止损价格、止盈价格。

    Args:
        signal:          "BUY" 或 "SELL"
        entry_price:     预计入场价（当前市价）
        trail:           Blackflag trail 线当前价格（作为止损位）
        account_balance: 账户净值（账户货币）
        risk_pct:        每单风险占账户余额的百分比（如 1.0 表示 1%）
        rr_ratio:        止盈/止损比例（如 2.0 表示 2:1）
        symbol_info:     品种合约规格

    Returns:
        (lots, sl_price, tp_price)
    """
    sl_distance = abs(entry_price - trail)
    risk_amount = account_balance * (risk_pct / 100.0)

    # 手数计算：risk_amount = lots × (sl_distance / tick_size) × tick_value
    sl_in_ticks = sl_distance / symbol_info.trade_tick_size
    raw_lots = risk_amount / (sl_in_ticks * symbol_info.trade_tick_value)

    # 对齐到手数步长，并限制在 [min, max] 范围
    step = symbol_info.volume_step
    lots = round(round(raw_lots / step) * step, 8)
    lots = max(lots, symbol_info.volume_min)
    lots = min(lots, symbol_info.volume_max)

    if signal == "BUY":
        sl = trail                              # 止损在入场下方
        tp = entry_price + sl_distance * rr_ratio
    else:
        sl = trail                              # 止损在入场上方
        tp = entry_price - sl_distance * rr_ratio

    return lots, round(sl, 8), round(tp, 8)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_risk_manager.py -v
```

Expected: 所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add risk_manager.py tests/test_risk_manager.py
git commit -m "feat: add risk manager with position sizing and SL/TP calculation"
```

---

## Task 6: Data Feed（MT5 数据拉取）

**Files:**
- Create: `data_feed.py`
- Create: `tests/test_data_feed.py`

注意：MT5 库在 Linux 环境下无法真实连接，测试使用 mock。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_data_feed.py`：

```python
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from data_feed import get_ohlcv, MT5_TIMEFRAME_MAP


class TestGetOhlcv:
    def _make_mt5_rates(self, n=10):
        """构造 MT5 copy_rates_from_pos 返回的数据格式"""
        import numpy as np
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
        mock_mt5.TIMEFRAME_M15 = 16385

        df = get_ohlcv("XAUUSD", "M15", bars=50)

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ['open', 'high', 'low', 'close']
        assert len(df) == 50

    @patch('data_feed.mt5')
    def test_raises_on_none(self, mock_mt5):
        mock_mt5.copy_rates_from_pos.return_value = None

        with pytest.raises(RuntimeError, match="Failed to fetch"):
            get_ohlcv("XAUUSD", "M15", bars=50)

    def test_timeframe_map_contains_m15(self):
        assert "M15" in MT5_TIMEFRAME_MAP
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_data_feed.py -v
```

Expected: `ImportError: No module named 'data_feed'`

- [ ] **Step 3: 实现 data_feed.py**

```python
import pandas as pd
import numpy as np

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # 允许在无 MT5 的环境下导入（测试时 mock）

MT5_TIMEFRAME_MAP = {
    "M1":  16385,
    "M5":  16388,
    "M15": 16390,
    "M30": 16392,
    "H1":  16408,
    "H4":  16416,
    "D1":  16424,
}


def get_ohlcv(symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
    """
    从 MT5 拉取历史 OHLCV 数据。

    Args:
        symbol:    品种代码，如 "XAUUSD"
        timeframe: 时间框架字符串，如 "M15"
        bars:      拉取的 K 线根数

    Returns:
        DataFrame，列为 ['open', 'high', 'low', 'close']，
        index 为 datetime（UTC），按时间升序，最新一根为最后一行。

    Raises:
        RuntimeError: 当 MT5 返回 None 时
    """
    tf = MT5_TIMEFRAME_MAP[timeframe]
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)

    if rates is None:
        raise RuntimeError(f"Failed to fetch OHLCV for {symbol} {timeframe}")

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time', inplace=True)
    df = df[['open', 'high', 'low', 'close']]
    return df
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_data_feed.py -v
```

Expected: 所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add data_feed.py tests/test_data_feed.py
git commit -m "feat: add MT5 data feed with OHLCV fetching"
```

---

## Task 7: Executor（MT5 下单管理）

**Files:**
- Create: `executor.py`
- Create: `tests/test_executor.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_executor.py`：

```python
import pytest
from unittest.mock import patch, MagicMock, call
from executor import has_open_position, place_order, get_symbol_info
from risk_manager import SymbolInfo


class TestHasOpenPosition:
    @patch('executor.mt5')
    def test_returns_true_when_position_exists(self, mock_mt5):
        mock_mt5.positions_get.return_value = (MagicMock(),)  # tuple，非空
        assert has_open_position("XAUUSD") is True

    @patch('executor.mt5')
    def test_returns_false_when_no_position(self, mock_mt5):
        mock_mt5.positions_get.return_value = ()
        assert has_open_position("XAUUSD") is False

    @patch('executor.mt5')
    def test_returns_false_when_none(self, mock_mt5):
        mock_mt5.positions_get.return_value = None
        assert has_open_position("XAUUSD") is False


class TestPlaceOrder:
    def _mock_mt5_buy(self, mock_mt5):
        mock_mt5.positions_get.return_value = []
        mock_mt5.ORDER_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        mock_mt5.TRADE_ACTION_DEAL = 1
        mock_mt5.ORDER_TIME_GTC = 1
        mock_mt5.ORDER_FILLING_IOC = 1
        tick = MagicMock()
        tick.ask = 2000.0
        tick.bid = 1999.5
        mock_mt5.symbol_info_tick.return_value = tick
        result = MagicMock()
        result.retcode = 10009  # TRADE_RETCODE_DONE
        mock_mt5.order_send.return_value = result
        return result

    @patch('executor.mt5')
    def test_buy_order_placed(self, mock_mt5):
        expected_result = self._mock_mt5_buy(mock_mt5)
        result = place_order("XAUUSD", "BUY", lots=0.01, sl=1900.0, tp=2200.0)
        assert mock_mt5.order_send.called
        assert result.retcode == 10009

    @patch('executor.mt5')
    def test_no_order_when_position_exists(self, mock_mt5):
        mock_mt5.positions_get.return_value = (MagicMock(),)
        result = place_order("XAUUSD", "BUY", lots=0.01, sl=1900.0, tp=2200.0)
        assert result is None
        mock_mt5.order_send.assert_not_called()


class TestGetSymbolInfo:
    @patch('executor.mt5')
    def test_returns_symbol_info(self, mock_mt5):
        info = MagicMock()
        info.trade_tick_value = 1.0
        info.trade_tick_size = 0.01
        info.volume_min = 0.01
        info.volume_max = 100.0
        info.volume_step = 0.01
        mock_mt5.symbol_info.return_value = info
        result = get_symbol_info("XAUUSD")
        assert isinstance(result, SymbolInfo)
        assert result.trade_tick_value == 1.0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_executor.py -v
```

Expected: `ImportError: No module named 'executor'`

- [ ] **Step 3: 实现 executor.py**

```python
import logging

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from risk_manager import SymbolInfo

logger = logging.getLogger(__name__)

MAGIC_NUMBER = 20260101  # 用于识别本系统的订单


def get_symbol_info(symbol: str) -> SymbolInfo:
    """从 MT5 获取品种合约规格。"""
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"Cannot get symbol info for {symbol}")
    return SymbolInfo(
        trade_tick_value=info.trade_tick_value,
        trade_tick_size=info.trade_tick_size,
        volume_min=info.volume_min,
        volume_max=info.volume_max,
        volume_step=info.volume_step,
    )


def has_open_position(symbol: str) -> bool:
    """检查该品种是否已有持仓（防重复开仓）。"""
    positions = mt5.positions_get(symbol=symbol)
    return bool(positions)


def place_order(
    symbol: str,
    signal: str,
    lots: float,
    sl: float,
    tp: float,
) -> object | None:
    """
    向 MT5 发送市价单。

    Returns:
        MT5 order_send 结果，若已有持仓则返回 None。
    """
    if has_open_position(symbol):
        logger.info(f"[{symbol}] Already has open position, skipping order.")
        return None

    if signal == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid

    request = {
        "action":      mt5.TRADE_ACTION_DEAL,
        "symbol":      symbol,
        "volume":      lots,
        "type":        order_type,
        "price":       price,
        "sl":          sl,
        "tp":          tp,
        "deviation":   20,
        "magic":       MAGIC_NUMBER,
        "comment":     "hma_blackflag_auto",
        "type_time":   mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != 10009:
        logger.error(f"[{symbol}] Order failed: retcode={result.retcode}, comment={result.comment}")
    else:
        logger.info(f"[{symbol}] {signal} order placed: {lots} lots, SL={sl}, TP={tp}")
    return result
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_executor.py -v
```

Expected: 所有测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add executor.py tests/test_executor.py
git commit -m "feat: add MT5 executor with order placement and duplicate prevention"
```

---

## Task 8: Scheduler + Main Entry（调度器与入口）

**Files:**
- Create: `scheduler.py`
- Create: `main.py`

- [ ] **Step 1: 实现 scheduler.py**

```python
import time
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from data_feed import get_ohlcv
from indicators.hma import hma, wma
from indicators.blackflag import blackflag
from signal_engine import get_signal
from risk_manager import calculate_trade_params
from executor import place_order, get_symbol_info

logger = logging.getLogger(__name__)


def run_once(symbol: str, cfg: dict) -> None:
    """
    拉取最新数据，计算指标，判断信号，下单。
    每根 15min K 线收盘后调用一次。
    """
    warmup = cfg['scheduler']['warmup_bars']
    hma_cfg = cfg['indicators']['hma']
    bf_cfg  = cfg['indicators']['blackflag']
    risk_cfg = cfg['risk']

    # 1. 拉取数据（多拉一根，用来确认收盘K线，index[-1]是正在形成的，index[-2]是刚收盘的）
    df = get_ohlcv(symbol, cfg['timeframe'], bars=warmup + 1)
    # 去掉最后一根（正在形成的K线），只用已收盘的K线
    df = df.iloc[:-1]

    close = df['close'].values
    high  = df['high'].values
    low   = df['low'].values

    # 2. 计算指标
    hma1 = hma(close, hma_cfg['length1'])
    hma2 = hma(close, hma_cfg['length2'])
    hma3 = hma(close, hma_cfg['length3'])
    trend, trail = blackflag(high, low, close,
                             atr_period=bf_cfg['atr_period'],
                             atr_factor=bf_cfg['atr_factor'])

    # 3. 判断信号
    signal = get_signal(hma1, hma2, hma3, trend)
    logger.info(f"[{symbol}] Signal: {signal}, HMA1={hma1[-1]:.4f}, "
                f"Trend={trend[-1]}, Trail={trail[-1]:.4f}")

    if signal == "HOLD":
        return

    # 4. 计算风险参数
    symbol_info = get_symbol_info(symbol)
    entry_price = close[-1]  # 用收盘价估算入场价
    lots, sl, tp = calculate_trade_params(
        signal=signal,
        entry_price=entry_price,
        trail=trail[-1],
        account_balance=mt5.account_info().balance,
        risk_pct=risk_cfg['risk_per_trade_pct'],
        rr_ratio=risk_cfg['rr_ratio'],
        symbol_info=symbol_info,
    )

    # 5. 下单
    place_order(symbol, signal, lots, sl, tp)


def start(cfg: dict) -> None:
    """
    主循环：每 poll_interval_seconds 秒检查一次是否有新收盘K线，
    有则对每个品种执行 run_once()。
    """
    symbols = cfg['symbols']
    interval = cfg['scheduler']['poll_interval_seconds']
    last_bar_time: dict[str, pd.Timestamp] = {s: None for s in symbols}

    logger.info("Scheduler started. Watching: %s", symbols)

    while True:
        for symbol in symbols:
            try:
                df = get_ohlcv(symbol, cfg['timeframe'], bars=2)
                # df[-1] 是正在形成的K线，df[-2] 是最新收盘的K线
                latest_closed_time = df.index[-2]

                if last_bar_time[symbol] != latest_closed_time:
                    last_bar_time[symbol] = latest_closed_time
                    logger.info(f"[{symbol}] New candle closed at {latest_closed_time}")
                    run_once(symbol, cfg)
            except Exception as e:
                logger.exception(f"[{symbol}] Error during run: {e}")

        time.sleep(interval)
```

- [ ] **Step 2: 实现 main.py**

```python
import logging
import sys
import yaml

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

import scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("trading.log"),
    ],
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def connect_mt5(cfg: dict) -> None:
    if not mt5.initialize():
        raise RuntimeError("MT5 initialize() failed")
    if not mt5.login(
        login=cfg['mt5']['login'],
        password=cfg['mt5']['password'],
        server=cfg['mt5']['server'],
    ):
        raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")
    info = mt5.account_info()
    logger.info(f"Connected to MT5: account={info.login}, balance={info.balance} {info.currency}")


def main():
    cfg = load_config()
    logger.info("Config loaded.")

    connect_mt5(cfg)

    try:
        scheduler.start(cfg)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        mt5.shutdown()
        logger.info("MT5 disconnected.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 运行所有测试确认无回归**

```bash
pytest tests/ -v
```

Expected: 所有测试 PASS，无 FAIL。

- [ ] **Step 4: 提交**

```bash
git add scheduler.py main.py
git commit -m "feat: add scheduler and main entry, complete trading system"
```

---

## Task 9: 指标验证（与 TradingView 对比）

**Files:**
- Create: `scripts/verify_indicators.py`

此步骤用于验证 Python 实现的指标数值与 TradingView 图表上显示的数值一致。

- [ ] **Step 1: 创建验证脚本**

创建 `scripts/verify_indicators.py`：

```python
"""
验证 Python 计算的 HMA 和 Blackflag 数值与 TradingView 一致。

用法：
  1. 连接 MT5（需要在 Windows 上或 Wine 环境下运行）
  2. python scripts/verify_indicators.py
  3. 将输出的最后 5 根K线数值与 TradingView 图表上的 Data Window 对比

TradingView Data Window 查看方法：
  - 打开 TradingView → 选择 XAUUSD 15min → 加载 HMA 和 Blackflag 指标
  - 按下 Ctrl+Shift+D 打开 Data Window
  - 将鼠标悬停在最近的几根K线上，记录指标数值与本脚本对比
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import yaml
import MetaTrader5 as mt5
from data_feed import get_ohlcv
from indicators.hma import hma
from indicators.blackflag import blackflag


def main():
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)

    mt5.initialize()
    mt5.login(cfg['mt5']['login'], cfg['mt5']['password'], cfg['mt5']['server'])

    symbol = "XAUUSD"
    df = get_ohlcv(symbol, "M15", bars=500)
    df = df.iloc[:-1]  # 去掉正在形成的K线

    close = df['close'].values
    high  = df['high'].values
    low   = df['low'].values

    hma1 = hma(close, 50)
    hma2 = hma(close, 100)
    hma3 = hma(close, 200)
    trend, trail = blackflag(high, low, close, atr_period=10, atr_factor=3)

    print(f"\n{'='*60}")
    print(f"最近 5 根已收盘 K 线的指标数值（{symbol} 15min）")
    print(f"{'='*60}")
    print(f"{'时间':<25} {'HMA1(50)':<12} {'HMA2(100)':<12} {'Trend':<8} {'Trail':<12}")
    print(f"{'-'*60}")
    for i in range(-5, 0):
        t = df.index[i].strftime('%Y-%m-%d %H:%M')
        print(f"{t:<25} {hma1[i]:<12.4f} {hma2[i]:<12.4f} {trend[i]:<8} {trail[i]:<12.4f}")

    mt5.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行验证脚本（需要 MT5 连接）**

```bash
python scripts/verify_indicators.py
```

与 TradingView 图表对比最近 3-5 根 K 线的数值，误差应 < 0.01%。

- [ ] **Step 3: 若有误差，排查原因**

常见误差来源：
- HMA 数据源：Pine Script 默认 `open`，用户改为 `close`，确认 `data_feed.py` 使用 `close`
- Blackflag Wilder MA 初始值：Pine Script 从 `0` 开始，Python 实现需保持一致
- K 线数量不足导致 Wilder MA 未收敛：增大 `warmup_bars`（建议至少 300）

- [ ] **Step 4: 提交验证脚本**

```bash
git add scripts/verify_indicators.py
git commit -m "chore: add indicator verification script for TradingView comparison"
```

---

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 运行所有单元测试
pytest tests/ -v

# 验证指标（需要 MT5 连接）
python scripts/verify_indicators.py

# 启动自动交易（需要 MT5 连接，建议先用模拟账户）
python main.py
```

---

## 注意事项

1. **MT5 仅支持 Windows**：在 Linux 上需通过 Wine 或远程调用运行，或直接在 Windows 机器上运行
2. **模拟账户测试**：实盘前务必在模拟账户运行至少 1-2 天
3. **指标预热**：Wilder MA 从 0 开始收敛，需要足够多的历史 K 线（建议 300 根以上）
4. **ORDER_FILLING 模式**：不同经纪商支持的成交模式不同，若下单失败 retcode=10030，改用 `ORDER_FILLING_FOK` 或 `ORDER_FILLING_RETURN`
