# Windows 容器镜像（需要 Docker Desktop 切换到 Windows containers 模式）
# 要求：Docker Desktop on Windows，Settings → Switch to Windows containers
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
