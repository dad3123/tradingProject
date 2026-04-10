# Kubernetes 部署指南

## 核心约束

`MetaTrader5` Python 包通过 **Windows Named Pipes** 与 MT5 终端通信，这意味着：

- 无法在标准 Linux Pod 中运行
- 网络方案（--network host、Service、Ingress）无法解决此问题
- MT5 终端与 Python bot 必须运行在同一 Windows 环境中

因此在 k8s 中有三种可行方案：

---

## 方案对比

| 方案 | 难度 | 适用场景 | 是否需要改代码 |
|------|------|----------|----------------|
| A. Windows 节点 + Windows 容器 | 中 | 已有 Windows 服务器 | 否 |
| B. Wine Linux 节点 | 高 | 只有 Linux 节点 | 否 |
| C. Bridge 桥接架构 | 高 | 生产环境、多账户 | 是 |

---

## 方案 A：Windows 节点（推荐）

### 原理

在 k8s 集群中加入 Windows 工作节点，把 Pod 调度到该节点上运行 Windows 容器。

```
k8s 集群
├── Linux 节点（运行其他服务）
└── Windows 节点（Windows Server 2022）
    └── trading-bot Pod（Windows 容器）
        ├── MT5 Terminal（Wine 或原生）
        └── Python bot
```

### 前提条件

- 一台 Windows Server 2019 或 2022 的节点加入 k8s 集群
- 支持 Windows 节点的 k8s 版本（1.14+，推荐 1.25+）
- 节点已安装 containerd 并配置好 Windows 容器运行时

### 部署步骤

**1. 确认集群有 Windows 节点**

```bash
kubectl get nodes -L kubernetes.io/os
```

应能看到 `windows` 的节点。

**2. 构建镜像并推送到镜像仓库**

```powershell
# 在 Windows 机器上构建（需要 Windows containers 模式）
docker build -f deploy/windows/Dockerfile -t your-registry/trading-bot:latest .
docker push your-registry/trading-bot:latest
```

**3. 部署**

```bash
kubectl apply -f deploy/k8s/deployment-windows.yaml
```

### 配置文件

见本目录的 `deployment-windows.yaml`。

---

## 方案 B：Wine Linux 节点

### 原理

在 Linux Pod 中用 Wine 模拟 Windows 环境，MT5 终端和 Python（Wine 版本）在同一容器中运行。

```
Linux 节点
└── trading-bot Pod（Linux 容器 + Wine）
    ├── Xvfb（虚拟显示）
    ├── Wine（模拟 Windows）
    │   ├── MT5 Terminal.exe
    │   └── Windows Python + MetaTrader5 包
    └── 启动脚本
```

### 缺点

- 镜像体积大（3-4 GB）
- Wine 兼容性不稳定，MT5 更新后可能失效
- 不适合生产环境

详见 `deployment-wine.yaml`（仅供参考，稳定性无法保证）。

---

## 方案 C：Bridge 桥接架构（最适合 k8s）

### 原理

将 MT5 通信层抽离到独立的 Windows 服务（集群外），k8s 内的 Python bot 通过 HTTP API 调用。

```
k8s 集群（Linux 节点）
└── trading-bot Pod
    ├── main.py（改造后不直接调用 mt5）
    ├── data_feed.py → HTTP → MT5 Bridge
    └── executor.py  → HTTP → MT5 Bridge

集群外 Windows 机器
└── mt5-bridge 服务（Python + Flask）
    ├── GET  /bars?symbol=BTCUSD&n=300   → mt5.copy_rates_from_pos()
    ├── POST /order  {symbol, lot, ...}  → mt5.order_send()
    └── GET  /account                   → mt5.account_info()
```

### 优势

- Python bot 运行在标准 Linux 容器中，完全符合 k8s 理念
- 可水平扩展 bot 实例（多账户、多策略）
- MT5 Bridge 单独维护，bot 代码不感知 Windows

### 需要改动的代码

`data_feed.py` 和 `executor.py` 中所有 `mt5.*` 调用改为 HTTP 请求：

```python
# 改造前（data_feed.py）
rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)

# 改造后
import requests
resp = requests.get(f"{BRIDGE_URL}/bars", params={"symbol": symbol, "n": n})
rates = resp.json()
```

Bridge 服务代码见 `mt5-bridge/` 目录（待实现）。

---

## 快速选择建议

```
有 Windows 服务器可以加入 k8s 集群？
├── 是 → 方案 A（Windows 节点）
└── 否
    ├── 只有 Linux 节点，可以接受不稳定？ → 方案 B（Wine）
    └── 需要稳定生产部署？ → 方案 C（Bridge，需改代码）
```
