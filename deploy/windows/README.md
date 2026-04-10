# Windows 部署指南

本指南说明如何在 Windows 电脑上通过 Docker Desktop 运行本交易程序。

---

## 前提条件

| 软件 | 版本要求 | 下载地址 |
|------|----------|----------|
| Windows | 10/11 (64位) | — |
| Docker Desktop | 最新版 | https://www.docker.com/products/docker-desktop |
| MetaTrader 5 终端 | 最新版 | https://www.metatrader5.com/en/download |
| Git | 最新版 | https://git-scm.com/download/win |

> **重要**：MetaTrader5 Python 包必须与 MT5 终端运行在**同一台 Windows 机器**上，
> 因此本方案采用「MT5 终端运行在 Windows 宿主机 + Python Bot 运行在 Docker 容器」架构，
> 通过共享网络通信。

---

## 架构说明

```
Windows 宿主机
├── MetaTrader 5 Terminal（直接安装，已登录账户）
└── Docker Desktop
    └── Python Bot 容器
        ├── main.py
        └── MetaTrader5 Python 包（连接宿主机上的 MT5）
```

---

## 第一步：安装并配置 MetaTrader 5

1. 下载并安装 MT5 终端
2. 打开 MT5，登录你的经纪商账户
3. 确保 MT5 保持**后台运行**状态
4. 在 MT5 中开启 AlgoTrading（工具栏上的「自动交易」按钮变绿）

---

## 第二步：安装 Docker Desktop

1. 下载并安装 Docker Desktop
2. 安装完成后重启电脑
3. 打开 Docker Desktop，等待其完全启动（系统托盘图标变为稳定状态）
4. 在设置中确认使用 **WSL 2 backend**（推荐）

验证安装：

```powershell
docker --version
docker run hello-world
```

---

## 第三步：获取项目代码

打开 PowerShell 或命令提示符：

```powershell
git clone <你的仓库地址> tradingProject
cd tradingProject
```

---

## 第四步：修改配置文件

编辑 `config.yaml`，填入你的账户信息：

```yaml
mt5:
  login: 12345678          # 你的 MT5 账号
  password: "your_password" # 你的 MT5 密码
  server: "ICMarkets-Demo"  # 你的经纪商服务器名称
```

---

## 前置说明：为什么必须用 Windows 容器

`MetaTrader5` Python 包**只有 Windows wheel**，无法在 Linux 容器中安装。
它通过 Windows 命名管道（Named Pipes）与 MT5 终端通信，这是 Windows 特有的 IPC 机制，
与网络无关，`--network host` 等网络参数无法解决此问题。

因此必须在 Docker Desktop 中切换到 **Windows containers 模式**。

---

## 第五步：切换到 Windows containers 模式

右键单击系统托盘中的 Docker 图标 → **Switch to Windows containers...**

> 切换后，`docker info` 中 `OSType` 应显示 `windows`

---

## 第六步：构建 Docker 镜像

在项目根目录下运行：

```powershell
docker build -f deploy/windows/Dockerfile -t trading-bot .
```

> 注意：首次构建需下载 Windows Server Core 基础镜像，体积约 **4-5 GB**，请耐心等待。

---

## 第七步：运行容器

```powershell
docker run -d `
  --name trading-bot `
  --isolation=process `
  -v "${PWD}/config.yaml:C:\app\config.yaml" `
  -v "${PWD}/trading.log:C:\app\trading.log" `
  trading-bot
```

参数说明：

| 参数 | 说明 |
|------|------|
| `--isolation=process` | 进程隔离模式，性能更好，与宿主机共享内核 |
| `-v config.yaml` | 挂载配置文件，修改后无需重新构建镜像 |
| `-v trading.log` | 挂载日志文件，方便在宿主机查看 |

> Windows 容器中的 MT5 终端需要**单独安装在容器内**或通过挂载卷提供，
> 因为 Named Pipes 不能跨主机边界通信。
> 最简单方案：把 MT5 终端和 Python bot 都放在同一个容器里运行。

---

## 第八步：查看运行状态

查看实时日志：

```powershell
docker logs -f trading-bot
```

正常启动后应看到类似输出：

```
2026-04-10 10:00:00 [INFO] Config loaded.
2026-04-10 10:00:00 [INFO] Connected to MT5: account=12345678, balance=10000.00 USD
2026-04-10 10:00:00 [INFO] Scheduler started.
```

---

## 常用管理命令

```powershell
# 停止容器
docker stop trading-bot

# 重新启动
docker start trading-bot

# 删除容器（镜像保留）
docker rm trading-bot

# 重新构建并运行（修改代码后）
docker build -f deploy/windows/Dockerfile -t trading-bot . && `
docker rm -f trading-bot && `
docker run -d --name trading-bot --isolation=process `
  -v "${PWD}/config.yaml:C:\app\config.yaml" `
  -v "${PWD}/trading.log:C:\app\trading.log" `
  trading-bot
```

---

## 常见问题排查

### MT5 连接失败

**错误**：`MT5 initialize() failed` 或 `MT5 login failed`

**原因及解决**：
- MT5 终端未运行 → 打开 MT5 终端并保持运行
- MT5 未登录 → 在终端中登录账户
- config.yaml 账号信息有误 → 检查 login/password/server 字段
- MT5 未允许自动交易 → 点击工具栏「自动交易」按钮

### MT5 终端与 Python bot 不在同一容器

`MetaTrader5` Python 包通过 **Windows Named Pipes** 与 MT5 终端通信，
这是 Windows 本地 IPC 机制，与网络无关。`--network host` 对此无效。
MT5 终端必须安装在**容器内部**，与 Python bot 运行在同一个容器中。

### 端口或权限问题

以**管理员权限**运行 PowerShell 后重试。

---

## 开机自启动（可选）

如果需要电脑重启后自动运行，在 `docker run` 命令中加入 `--restart unless-stopped`：

```powershell
docker run -d `
  --name trading-bot `
  --isolation=process `
  --restart unless-stopped `
  -v "${PWD}/config.yaml:C:\app\config.yaml" `
  -v "${PWD}/trading.log:C:\app\trading.log" `
  trading-bot
```

同时需确保 Docker Desktop 设置为**开机自启动**（Settings → General → Start Docker Desktop when you log in）。

---

## 目录结构

```
deploy/
└── windows/
    ├── README.md        # 本文件
    └── Dockerfile       # Docker 镜像构建文件
```
