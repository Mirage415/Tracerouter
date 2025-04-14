#!/bin/sh

# 启用IP转发
sysctl -w net.ipv4.ip_forward=1

# 等待网络接口准备好
sleep 5

# 显示所有网络接口
echo "当前网络接口:"
ip addr

# 尝试发现其他主机
echo "尝试发现其他主机..."
for host in r2 r3 r4 server1 client1; do
  ping -c 1 $host > /dev/null 2>&1
  if [ $? -eq 0 ]; then
    echo "$host 可达"
  fi
done

# 显示当前路由表
echo "当前路由表:"
ip route

# 添加所有可能的路由
for net in $(ip -4 route | grep -v "dev lo" | grep -v "default" | awk '{print $1}'); do
  echo "发现网络: $net"
done

# 设置路由
# 通过r3添加路由
ip route add 192.168.103.0/24 via 192.168.101.101 dev eth1 || true
ip route add 192.168.105.0/24 via 192.168.101.101 dev eth1 || true

# 通过r4添加路由
ip route add 192.168.104.0/24 via 192.168.102.101 dev eth2 || true 
ip route add 192.168.106.0/24 via 192.168.102.101 dev eth2 || true

echo "路由器r1设置完成!"
ip route 