FROM python:3.9-slim

WORKDIR /app

# 安装必要的工具
RUN apt-get update && apt-get install -y \
    iproute2 \
    iputils-ping \
    net-tools \
    traceroute \
    tcpdump \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir numpy==1.23.5 && \
    pip install --no-cache-dir -r requirements.txt

# 工作目录
WORKDIR /app

CMD ["/bin/bash"] 