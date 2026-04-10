# MT5 自动交易系统

基于 MetaTrader5 的 Python 量化自动交易系统，针对 **BTCUSD** 和 **XAUUSD** 在 **15 分钟**时间框架上运行，集成 HMA + Blackflag FTS 双指标策略，支持实盘交易和历史回测两种模式。

---

## 功能特性

- **双指标策略**：HMA (Hull Moving Average) 三均线系统 + Blackflag FTS 追踪止损指标
- **多品种支持**：可配置多个交易品种（默认 BTCUSD、XAUUSD）
- **动态风险管理**：按账户余额百分比计算手数，固定盈亏比止盈
- **历史回测**：按日期范围回测，输出含胜率、最大回撤的完整报告
- **模式切换**：通过配置文件一键切换实盘 / 回测模式

---

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | **Windows**（MetaTrader5 仅有 Windows wheel） |
| Python | 3.10+ |
| MT5 终端 | 需安装并登录，开启 AlgoTrading |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置账号

编辑 `config.yaml`，填入 MT5 账号信息：

```yaml
mt5:
  login: 12345678
  password: "your_password"
  server: "ICMarkets-Demo"
```

### 3. 选择模式并运行

```bash
python main.py
```

---

## 配置文件说明

```yaml
mode: backtest             # live（实盘）| backtest（回测）

backtest:
  start_date: "2025-10-10" # 回测开始日期
  end_date:   "2026-04-10" # 回测结束日期
  initial_balance: 10000.0 # 回测初始资金（null 则使用账户实际余额）

mt5:
  login: 12345678
  password: "your_password"
  server: "ICMarkets-Demo"

symbols:
  - BTCUSD
  - XAUUSD

timeframe: M15             # K 线周期

indicators:
  hma:
    length1: 50            # 快速均线
    length2: 100           # 中速均线
    length3: 200           # 慢速均线（趋势过滤）
    source: close
  blackflag:
    trail_type: modified   # modified（修正 ATR）| standard
    atr_period: 10
    atr_factor: 3

risk:
  risk_per_trade_pct: 1.0  # 每单风险占账户余额的百分比
  rr_ratio: 2.0            # 止盈/止损比例

scheduler:
  poll_interval_seconds: 30
  warmup_bars: 300         # 启动时拉取的历史 K 线数（用于指标预热）
```

---

## 交易策略

### 入场条件（三重确认）

| 信号 | 条件 1 | 条件 2 | 条件 3 |
|------|--------|--------|--------|
| **BUY** | HMA(50) 上穿 HMA(100) | HMA(50) > HMA(200) | Blackflag Trend = +1 |
| **SELL** | HMA(50) 下穿 HMA(100) | HMA(50) < HMA(200) | Blackflag Trend = −1 |

### 止损与止盈

- **止损价**：Blackflag trail 线当前价格
- **止盈价**：入场价 ± 止损距离 × `rr_ratio`（默认 2:1）
- **手数**：`账户余额 × risk_per_trade_pct% ÷ (止损距离 × tick_value)`

---

## 项目结构

```
tradingProject/
├── main.py              # 入口：根据 mode 分发至实盘或回测
├── config.yaml          # 所有配置
├── scheduler.py         # 实盘主循环（每 30 秒轮询 K 线收盘）
├── data_feed.py         # MT5 数据拉取（按 bar 数 / 日期范围）
├── signal_engine.py     # 信号合并逻辑 → BUY / SELL / HOLD
├── risk_manager.py      # 仓位、止损、止盈计算
├── executor.py          # MT5 下单、持仓检查
├── indicators/
│   ├── hma.py           # Hull Moving Average
│   └── blackflag.py     # Blackflag FTS（修正 ATR + 追踪止损）
├── scripts/
│   └── backtest.py      # 历史回测，结果输出至 backtest_results.txt
├── tests/               # 单元测试（pytest）
└── deploy/
    ├── windows/         # Windows Docker 部署方案
    └── k8s/             # Kubernetes 部署方案
```

---

## 回测

将 `config.yaml` 中 `mode` 设为 `backtest`，配置日期范围后运行：

```bash
python main.py
```

回测结果保存在项目根目录 `backtest_results.txt`，包含：

- 每笔交易的入场/出场时间、价格、手数、盈亏
- 总交易次数、胜率、净盈亏
- 最大连续亏损次数、最大回撤

---

## 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行单个模块测试
pytest tests/test_hma.py -v
pytest tests/test_blackflag.py -v
```

---

## 部署

| 方案 | 说明 |
|------|------|
| **Windows 本地** | 直接 `python main.py` |
| **Windows Docker** | 参见 [deploy/windows/README.md](deploy/windows/README.md) |
| **Kubernetes** | 参见 [deploy/k8s/README.md](deploy/k8s/README.md) |

> **注意**：所有部署方案均需要 Windows 环境，因为 MetaTrader5 Python 包仅支持 Windows。

---

## 日志

运行时日志同时输出到控制台和 `trading.log` 文件。
