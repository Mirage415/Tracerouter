#!/bin/sh

# 启用IP转发
sysctl -w net.ipv4.ip_forward=1

# 显示所有网络接口
echo "当前网络接口:"
ip addr

# 设置路由
# 通过r1添加路由
ip route add 192.168.100.0/24 via 192.168.101.100 dev eth0 || true
ip route add 192.168.102.0/24 via 192.168.101.100 dev eth0 || true

# 通过r2添加路由
ip route add 192.168.104.0/24 via 192.168.103.100 dev eth1 || true

# 通过r4添加路由
ip route add 192.168.106.0/24 via 192.168.105.101 dev eth2 || true

echo "路由器r3设置完成!"
ip route 