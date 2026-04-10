# Windows 本地运行指南（无需 Docker）

直接在 Windows 机器上运行，MT5 终端与 Python Bot 同在一台电脑，通过 Named Pipes 本地通信，最简单可靠。

---

## 前提条件

| 软件 | 版本要求 | 下载地址 |
|------|----------|----------|
| Windows | 10/11 (64位) | — |
| Python | 3.10+ | https://www.python.org/downloads/ |
| MetaTrader 5 终端 | 最新版 | https://www.metatrader5.com/en/download |
| Git | 最新版 | https://git-scm.com/download/win |

---

## 第一步：安装 Python

1. 打开上方链接下载 Python 3.10+（选 **Windows installer (64-bit)**）
2. 运行安装程序，**务必勾选** `Add Python to PATH`
3. 点击 `Install Now`

验证安装（打开 PowerShell）：

```powershell
python --version
# 应输出：Python 3.10.x 或更高
```

---

## 第二步：安装并配置 MetaTrader 5

1. 下载并安装 MT5 终端
2. 打开 MT5，登录你的经纪商账户
3. 点击工具栏的「**自动交易**」按钮，确保它变为**绿色**（已启用 AlgoTrading）
4. 保持 MT5 终端在后台运行（不要关闭）

---

## 第三步：获取项目代码

打开 PowerShell，`cd` 到你想存放项目的目录：

```powershell
git clone https://github.com/dad3123/tradingProject.git
cd tradingProject
```

---

## 第四步：创建虚拟环境并安装依赖

```powershell
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

> 如果执行 `Activate.ps1` 报"无法加载文件，因为在此系统上禁止运行脚本"，先运行：
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
> 然后重新激活。

---

## 第五步：修改配置文件

用记事本或任意编辑器打开项目根目录的 `config.yaml`：

```yaml
mode: live                 # live = 实盘/模拟盘交易；backtest = 历史回测

mt5:
  login: 12345678          # 你的 MT5 账号（数字）
  password: "your_password" # 你的 MT5 密码
  server: "ICMarkets-Demo"  # 经纪商服务器名称（MT5 登录界面可查）
```

> 服务器名称在 MT5 登录窗口的「服务器」下拉框中可以看到，例如 `ICMarkets-Demo`、`Pepperstone-Demo` 等。

---

## 第六步：运行程序

确保虚拟环境已激活（PowerShell 提示符前有 `(.venv)`），然后：

```powershell
python main.py
```

正常启动后应看到：

```
2026-04-10 10:00:00 [INFO] Mode: live
2026-04-10 10:00:00 [INFO] Connected to MT5: account=12345678, balance=10000.00 USD
2026-04-10 10:00:00 [INFO] [BTCUSD] Scheduler started, poll_interval=30s
2026-04-10 10:00:00 [INFO] [XAUUSD] Scheduler started, poll_interval=30s
```

程序会每 30 秒检查一次 K 线是否收盘，收盘时自动计算信号并下单。

按 `Ctrl+C` 可安全停止程序。

---

## 运行回测

将 `config.yaml` 中 `mode` 改为 `backtest`，设置好日期范围：

```yaml
mode: backtest

backtest:
  start_date: "2025-10-10"
  end_date:   "2026-04-10"
  initial_balance: 10000.0
```

然后运行：

```powershell
python main.py
```

回测完成后，结果保存在项目根目录的 `backtest_results.txt` 中。

---

## 查看日志

运行时日志同时输出到控制台和 `logs\trading.log` 文件：

```powershell
# 实时查看日志文件（类似 Linux tail -f）
Get-Content logs\trading.log -Wait -Tail 50
```

---

## 开机自启动（可选）

如果希望电脑开机后自动运行，可用 Windows 任务计划程序：

1. 打开「任务计划程序」（搜索栏输入 `taskschd.msc`）
2. 点击「创建基本任务」
3. 触发器选「登录时」
4. 操作选「启动程序」，填入：
   - 程序：`C:\path\to\tradingProject\.venv\Scripts\python.exe`
   - 参数：`main.py`
   - 起始位置：`C:\path\to\tradingProject`
5. 勾选「以最高权限运行」

> 注意：MT5 终端也需要设置为开机自启动，且需先于 Python Bot 启动完成并登录账户。

---

## 常见问题

### `MT5 initialize() failed`
- MT5 终端未运行 → 打开 MT5 保持后台运行
- MT5 未登录账户 → 在终端中登录

### `MT5 login failed`
- 账号/密码/服务器名称填写有误 → 检查 `config.yaml` 中三个字段
- 服务器名称区分大小写，需与 MT5 登录界面完全一致

### `ModuleNotFoundError: No module named 'MetaTrader5'`
- 虚拟环境未激活 → 重新运行 `.venv\Scripts\Activate.ps1`
- 运行在 macOS/Linux → MetaTrader5 包仅支持 Windows

### 信号有但没有下单
- MT5「自动交易」按钮未开启（不是绿色）→ 点击开启
- 账户余额不足以计算最小手数 → 检查 `risk_per_trade_pct` 配置
