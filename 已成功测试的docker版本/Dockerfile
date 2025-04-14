FROM python:3.9-slim

WORKDIR /app

# 安装必要的系统包和Python依赖
RUN apt-get update && apt-get install -y \
    iputils-ping \
    net-tools \
    traceroute \
    dnsutils \
    tcpdump \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
COPY traceroute.py .

# 安装Python依赖 - 确保numpy和pandas版本兼容
RUN pip install --no-cache-dir numpy==1.23.5 && \
    pip install --no-cache-dir -r requirements.txt

# 设置入口点
ENTRYPOINT ["python", "traceroute.py"] 