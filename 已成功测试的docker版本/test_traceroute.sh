#!/bin/bash

# 确保脚本可执行
chmod +x ./traceroute.py

# 等待所有容器启动和配置
echo "等待容器启动和网络配置..."
sleep 10

# 检查所有容器是否在运行
echo "检查容器状态..."
docker ps

# 测试服务器连通性
echo "测试server1连通性..."
docker exec -it client1 ping -c 3 192.168.100.200 || echo "无法连接到server1"

# 显示client1的网络配置
echo "客户端网络配置:"
docker exec -it client1 ip addr
docker exec -it client1 ip route

# 执行traceroute测试
echo "执行traceroute测试 (服务器)..."
docker exec -it client1 python3 /app/traceroute.py -t 192.168.100.200

# 测试使用不同协议
echo "使用UDP协议..."
docker exec -it client1 python3 /app/traceroute.py -t 192.168.100.200 -P udp

echo "使用TCP协议..."
docker exec -it client1 python3 /app/traceroute.py -t 192.168.100.200 -P tcp

echo "使用ICMP协议..."
docker exec -it client1 python3 /app/traceroute.py -t 192.168.100.200 -P icmp

# 执行批量测试
echo "批量执行traceroute测试 (从文件)..."
docker exec -it client1 python3 /app/traceroute.py -f /app/target_ips.txt

echo "测试完成!" 