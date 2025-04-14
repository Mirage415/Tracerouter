#!/bin/sh

# 显示所有网络接口
echo "当前网络接口:"
ip addr

# 设置默认路由
ip route del default 2>/dev/null || true
ip route add default via 192.168.106.100 dev eth0 || true

# 检查连通性
echo "测试路由器连通性..."
ping -c 1 -W 2 192.168.106.100 || echo "无法连接到r4"

echo "客户端设置完成!"
ip route
