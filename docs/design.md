# TradingView Indicators → MT5 自动交易系统 设计文档

**日期**: 2026-04-10  
**状态**: 已确认，待实现

---

## 背景与目标

用户希望构建一个自动化交易系统，将 TradingView 图表上的两个技术指标（HMA 和 Blackflag FTS）的信号逻辑在 Python 中复现，并通过 MT5 API 自动执行 BTCUSD 和 XAUUSD 的交易，无需浏览器抓取，直接从 MT5 本地拉取行情数据计算指标。

---

## 交易品种与参数

| 品种 | 时间框架 | 特性 |
|------|----------|------|
| BTCUSD | 15分钟 | 加密货币 |
| XAUUSD | 15分钟 | 黄金/外汇 |

---

## 指标参数

### HMA 指标（Hull Moving Average）

来源：[TradingView](https://cn.tradingview.com/script/BxQKhnlc-HMA-WMA-2-WMA-n-2-WMA-n-sqrt-n/)  
公式：`HMA(n) = WMA(2×WMA(n/2) − WMA(n), √n)`

| 参数 | 值 |
|------|----|
| Length1 (HMA1) | 50 |
| Length2 (HMA2) | 100 |
| Length3 (HMA3) | 200 |
| 数据源 | 收盘价 (close) |

**视觉逻辑：**
- 圆点出现 = HMA1 穿越 HMA2（`cross(hullma, hullma2)` 为 True）
- 石灰绿圆点 = HMA1 > HMA2（看涨穿越）
- 红色圆点 = HMA1 < HMA2（看跌穿越）
- 云朵颜色 = `HMA1 > HMA3 ? green : red`（用于趋势过滤）

### Blackflag FTS 指标（SwingArm ATR Trend）

来源：[TradingView](https://cn.tradingview.com/script/Dxc0Pi3n-SwingArm-ATR-Trend-Indicator/)

| 参数 | 值 |
|------|----|
| Trail Type | modified |
| ATR Period | 10 |
| ATR Factor | 3 |

**核心逻辑（Python 复现）：**
```
Modified True Range:
  HiLo = min(H-L, 1.5 × SMA(H-L, ATRPeriod))
  HRef = H - C[1]（或调整版本）
  LRef = C[1] - L（或调整版本）
  trueRange = max(HiLo, HRef, LRef)

Wilder's MA:
  wild[i] = wild[i-1] + (trueRange - wild[i-1]) / ATRPeriod

Trailing Stop:
  loss = ATRFactor × wild
  Up = close - loss
  Dn = close + loss
  TrendUp = max(Up, TrendUp[1])  若 close[1] > TrendUp[1]，否则 Up
  TrendDown = min(Dn, TrendDown[1])  若 close[1] < TrendDown[1]，否则 Dn

Trend Direction:
  Trend = 1  若 close > TrendDown[1]
  Trend = -1 若 close < TrendUp[1]
  否则维持上一状态

trail = TrendUp 若 Trend==1，否则 TrendDown
```

---

## 入场信号逻辑

### 做多（BUY）
所有三个条件同时满足：
1. HMA1(50) 本根K线 **上穿** HMA2(100)（前一根 HMA1 < HMA2，当前 HMA1 > HMA2）
2. HMA1(50) **> HMA3(200)**（云朵为绿，整体上升趋势，过滤震荡）
3. Blackflag `Trend == 1`（绿色追踪线，上升趋势确认）

### 做空（SELL）
所有三个条件同时满足：
1. HMA1(50) 本根K线 **下穿** HMA2(100)
2. HMA1(50) **< HMA3(200)**（云朵为红，整体下降趋势，过滤震荡）
3. Blackflag `Trend == -1`（红色追踪线，下降趋势确认）

### 震荡行情过滤
条件 2（HMA1 vs HMA3）天然过滤震荡：震荡时 HMA1 在 HMA3 附近来回穿越，不会稳定地在 HMA3 一侧。

---

## 风险管理

| 参数 | 说明 |
|------|------|
| 每单风险比例 | 账户余额的 N%（可在 config.yaml 中配置，建议 1%） |
| 止损（SL） | 入场时 Blackflag `trail` 线的当前价格（固定，不追踪） |
| 止盈（TP） | 入场价 ± SL距离 × 2（固定 2:1 风险回报比） |
| 仓位大小 | `(账户余额 × 风险%) / (SL距离 × 合约价值)` |

---

## 系统架构

```
MT5 行情数据 (15min OHLCV)
        ↓
┌─────────────────────────────────┐
│          indicators/            │
│  hma.py        → HMA1/2/3值     │
│  blackflag.py  → Trend, trail   │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│         signal_engine.py        │
│  合并信号 → BUY / SELL / HOLD   │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│         risk_manager.py         │
│  计算 lots、SL价格、TP价格       │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│           executor.py           │
│  MT5 下单 / 检查持仓 / 防重复   │
└─────────────────────────────────┘
             ↑
┌─────────────────────────────────┐
│          scheduler.py           │
│  每根15min K线收盘后触发一次     │
│  BTCUSD 和 XAUUSD 分别检测      │
└─────────────────────────────────┘
```

---

## 项目文件结构

```
tradingProject/
├── config.yaml              # 所有可配置参数
├── main.py                  # 入口，启动调度器
├── data_feed.py             # MT5 API 拉取 OHLCV 数据
├── indicators/
│   ├── __init__.py
│   ├── hma.py               # HMA 计算（WMA 嵌套）
│   └── blackflag.py         # Blackflag FTS 计算（修正 ATR + 追踪止损）
├── signal_engine.py         # 信号合并逻辑
├── risk_manager.py          # 仓位大小、SL/TP 计算
├── executor.py              # MT5 下单、持仓管理
├── scheduler.py             # 15min 定时触发
└── docs/
    └── superpowers/specs/
        └── 2026-04-10-tradingview-mt5-autotrader-design.md
```

---

## config.yaml 关键参数

```yaml
mt5:
  login: YOUR_LOGIN
  password: YOUR_PASSWORD
  server: YOUR_BROKER_SERVER

symbols:
  - BTCUSD
  - XAUUSD

timeframe: M15

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
  risk_per_trade_pct: 1.0   # 每单风险 1% 账户余额
  rr_ratio: 2.0             # 止盈为止损的 2 倍
```

---

## 技术栈

| 组件 | 工具 |
|------|------|
| 语言 | Python 3.10+ |
| MT5 接口 | `MetaTrader5` 官方 Python 库 |
| 数据处理 | `pandas`, `numpy` |
| 调度 | `schedule` 或 `APScheduler` |
| 配置 | `pyyaml` |
| 日志 | Python `logging` 模块 |

---

## 验证方案

1. **指标对比验证**：用历史数据计算 HMA 和 Blackflag，与 TradingView 图表上的数值逐根比对，误差应 < 0.01%
2. **信号回测**：在历史数据上运行信号引擎，打印每次触发的 BUY/SELL 信号，人工抽查与图表对比
3. **纸交易测试**：连接 MT5 模拟账户，运行 1-2 天，验证下单逻辑、SL/TP 设置正确
4. **实盘小仓位**：确认无误后以最小手数开始实盘

---

## 核心约束

- **防重复下单**：同一品种已有持仓时，不重复开仓
- **K线收盘检测**：只在 15min K线收盘那一刻检测信号，避免同一根K线重复触发
- **MT5 连接断线重连**：调度器需处理 MT5 断线异常并自动重连
