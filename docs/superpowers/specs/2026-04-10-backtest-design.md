# 回测功能设计文档

**日期**: 2026-04-10  
**状态**: 已确认，待实现

---

## 目标

在最近6个月的历史K线数据上，模拟运行现有交易策略（HMA + Blackflag FTS），统计每笔交易的明细和整体表现，输出到 `backtest_results.txt` 文件供人工审阅。

---

## 范围与约束

- **品种**：BTCUSD、XAUUSD（与实盘一致）
- **时间框架**：15分钟K线
- **回测周期**：最近6个月（从 MT5 拉取历史数据）
- **数据来源**：MT5 API（`data_feed.get_ohlcv()`）
- **入场价**：信号触发那根K线的收盘价（模拟K线收盘时入场）
- **出场逻辑**：逐根后续K线检查 high/low，先触达 SL 则止损出场，先触达 TP 则止盈出场
- **防重复开仓**：同一品种有持仓期间，不触发新信号
- **不修改任何现有文件**，仅新增 `scripts/backtest.py`

---

## 架构

```
MT5 历史K线（最近6个月 + 300根 warmup，15min）
        ↓
逐根K线遍历（从第 warmup_bars 根开始）
        ↓
  indicators/hma.py        → hma1, hma2, hma3
  indicators/blackflag.py  → trend, trail
        ↓
  signal_engine.get_signal() → BUY / SELL / HOLD
        ↓
  risk_manager.calculate_trade_params() → lots, sl, tp
        ↓
  模拟出场：逐根后续K线检查 high/low vs SL/TP
        ↓
  汇总统计 → backtest_results.txt
```

复用模块：`data_feed`、`indicators/hma`、`indicators/blackflag`、`signal_engine`、`risk_manager`

---

## 数据拉取

```python
# 最近6个月 15min K线根数估算：
# 6个月 × 30天 × 24小时 × 4根/小时 = 17280根
# 加 warmup_bars（300根）= 17580根
BACKTEST_BARS = 17580
WARMUP_BARS   = 300  # 读自 config.yaml scheduler.warmup_bars
```

用 `data_feed.get_ohlcv(symbol, timeframe, bars=BACKTEST_BARS)` 拉取，不去掉最后一根（历史数据全部已收盘）。

---

## 核心回测循环

```
对每根 K 线 i（从 WARMUP_BARS 到 len(df)-1）：
  用 df[:i+1] 计算指标（全量滑窗）
  调用 get_signal() 得到 signal
  若当前无持仓 且 signal != HOLD：
    entry_price = df.close[i]
    lots, sl, tp = calculate_trade_params(...)
    记录开仓信息
    从 i+1 开始逐根检查出场：
      若 low[j] <= sl → 止损出场，exit_price = sl
      若 high[j] >= tp → 止盈出场，exit_price = tp
      若遍历完全部K线仍未出场 → 标记为"持仓中（未出场）"
    计算盈亏：
      BUY:  pnl_points = exit_price - entry_price
      SELL: pnl_points = entry_price - exit_price
      pnl_usd = pnl_points / tick_size × tick_value × lots
```

---

## 输出格式（backtest_results.txt）

```
========================================
回测报告 - BTCUSD
回测区间：2025-10-10 00:00 ~ 2026-04-10 00:00
初始资金：$10,000.00
========================================

【交易明细】
#   方向  入场时间              入场价      手数   止损价      止盈价      出场时间              出场价      出场原因  盈亏(点)   盈亏(USD)
1   BUY   2025-10-15 09:00     65000.00   0.01   64500.00   66000.00  2025-10-15 14:00     66000.00   止盈      +1000.00   +100.00
2   SELL  2025-10-20 03:15     66500.00   0.01   67000.00   65500.00  2025-10-20 05:30     67000.00   止损      -500.00    -50.00
...

【汇总统计】
总交易次数：  12
盈利次数：    8    胜率：66.7%
亏损次数：    4
未出场次数：  0

每笔平均手数：0.01

总盈利：   +$850.00
总亏损：   -$200.00
净盈亏：   +$650.00

平均单笔盈利：+$106.25
平均单笔亏损：-$50.00

最大连续亏损次数：2
最大回撤：       -$200.00 (-2.0%)

========================================

========================================
回测报告 - XAUUSD
...
========================================
```

---

## 文件变动

| 文件 | 操作 |
|------|------|
| `scripts/backtest.py` | **新增** |
| 其他所有文件 | 不动 |

---

## 仓位计算说明

每笔交易的手数均以**MT5 账户当前余额（初始余额）**为基准计算，回测期间不随盈亏动态更新。这与"每单固定风险1%"的静态仓位管理一致，结果更清晰可控。

---

## 风险说明

- **滑点未模拟**：实盘入场价可能与K线收盘价有差异
- **点差未计入**：实盘有买卖价差成本
- **持仓中未出场**：若回测结束时仍有持仓，单独标注，不计入统计
- **手数精度**：使用 `risk_manager` 现有的 volume_step 对齐逻辑

---

## 运行方式

```bash
python scripts/backtest.py
# 结果写入 backtest_results.txt（项目根目录）
```

需要 MT5 已连接（Windows 环境）。
