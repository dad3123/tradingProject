# Windows 容器镜像（需要 Docker Desktop 切换到 Windows containers 模式）
# 要求：Docker Desktop on Windows，Settings → Switch to Windows containers
#
# 注意：MetaTrader5 Python 包通过 Windows Named Pipes 与 MT5 终端通信，
#       两者必须运行在同一容器内。本镜像仅包含 Python Bot；
#       MT5 终端需在容器首次启动后手动安装，或通过自定义基础镜像预置。
FROM mcr.microsoft.com/windows/servercore:ltsc2022

SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop';"]

# 安装 Python 3.10
RUN Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe `
      -OutFile C:\python-installer.exe ; `
    Start-Process C:\python-installer.exe `
      -ArgumentList '/quiet', 'InstallAllUsers=1', 'PrependPath=1' `
      -Wait ; `
    Remove-Item C:\python-installer.exe

WORKDIR C:\app

# 创建日志目录（通过卷挂载持久化到宿主机）
RUN New-Item -ItemType Directory -Path C:\app\logs -Force | Out-Null

# 安装 Python 依赖（MetaTrader5 有 Windows wheel，可以正常安装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY indicators\ .\indicators\
COPY signal_engine.py .
COPY data_feed.py .
COPY executor.py .
COPY risk_manager.py .
COPY scheduler.py .
COPY main.py .

# config.yaml 通过卷挂载，不打包进镜像
CMD ["python", "main.py"]
