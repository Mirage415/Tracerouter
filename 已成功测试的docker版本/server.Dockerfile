FROM ubuntu:20.04

# 避免交互式提示
ENV DEBIAN_FRONTEND=noninteractive

# 安装必要的网络工具
RUN apt-get update && apt-get install -y \
    iproute2 \
    iputils-ping \
    net-tools \
    procps \
    tcpdump \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
RUN pip3 install scapy

WORKDIR /app

CMD ["tail", "-f", "/dev/null"] 