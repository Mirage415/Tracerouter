FROM ubuntu:20.04

# 避免交互式提示
ENV DEBIAN_FRONTEND=noninteractive

# 安装必要的网络工具
RUN apt-get update && apt-get install -y \
    iproute2 \
    iputils-ping \
    net-tools \
    traceroute \
    tcpdump \
    iptables \
    procps \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
RUN pip3 install scapy dnspython

# 启用IP转发
RUN echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

WORKDIR /app

CMD ["/bin/bash"] 