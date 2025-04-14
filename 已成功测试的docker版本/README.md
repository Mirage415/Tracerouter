# 自定义 Traceroute 探测工具

这个项目包含一个自定义的Traceroute探测工具，可以使用不同协议（UDP、TCP、ICMP）探测网络路径，以及一个基于Docker Compose的网络拓扑测试环境。

## 项目结构

- `traceroute.py` - 自定义Traceroute探测工具
- `Dockerfile` - 单容器Docker构建文件
- `docker-compose.yml` - 多容器网络拓扑配置
- `router.Dockerfile`, `server.Dockerfile`, `client.Dockerfile` - 各节点的Docker配置
- `r1_setup.sh`, `r2_setup.sh`... - 路由器配置脚本
- `client1_setup.sh`, `server1_setup.sh` - 客户端和服务器配置脚本
- `requirements.txt` - Python依赖
- `target_ips.txt` - 测试目标IP地址列表
- `test_traceroute.sh` - 测试脚本

## 网络拓扑结构

该项目配置了一个包含4个路由器、1个客户端和1个服务器的网络拓扑：

```
网络拓扑图解释:
- net-a (192.168.100.0/24): r1, r2, server1
- net-b (192.168.101.0/24): r1, r3
- net-c (192.168.102.0/24): r1, r4
- net-d (192.168.103.0/24): r2, r3
- net-e (192.168.104.0/24): r2, r4
- net-f (192.168.105.0/24): r3, r4
- net-g (192.168.106.0/24): r4, client1

     server1
   (192.168.100.200)
        |
    net-a (192.168.100.0/24)
        |
 ----------------
 |              |
 r1             r2
(192.168.100.100)  (192.168.100.101)
 |  \          /  \
 |   \        /    \
 |    \      /      \
 |     \    /        \
 |      \  /          \
net-b   net-c        net-d     net-e
 |        |          |         |
 |        |          |         |
 r3-------|---------r3         r4
(192.168.101.101)    (192.168.103.101) (192.168.104.101)
 \                   /          /
  \                 /          /
   \               /          /
    \             /          /
     \           /          /
     net-f (192.168.105.0/24)  
       \         /        
        \       /        
         \     /        
          \   /        
           \ /        
           r4         
      (192.168.105.101)
            |
       net-g (192.168.106.0/24)
            |
         client1
      (192.168.106.200)
```

## 使用方法

### 1. 单容器模式

如果您只想运行traceroute工具，无需网络拓扑：

```bash
# 构建Docker镜像
docker build -t custom-traceroute .

# 运行单个IP的traceroute
docker run --cap-add=NET_RAW custom-traceroute -t 8.8.8.8

# 使用文件中的IP列表
docker run --cap-add=NET_RAW -v $(pwd)/target_ips.txt:/app/target_ips.txt custom-traceroute -f target_ips.txt
```

### 2. 多容器网络拓扑模式

如果您想在模拟网络环境中测试：

```bash
# 停止所有运行中的容器
docker-compose down

# 清理所有Docker资源
docker rm -f $(docker ps -aq)
docker network prune -f

# 启动整个网络拓扑
docker-compose up -d

# 运行测试脚本
chmod +x test_traceroute.sh
./test_traceroute.sh

# 手动进入客户端容器
docker exec -it client1 bash

# 在客户端容器中运行traceroute
python3 /app/traceroute.py -t 192.168.100.200

# 清理环境
docker-compose down
```

## Traceroute工具参数

- `-t, --target` - 指定目标IP地址或主机名（可多次使用）
- `-f, --file` - 指定包含目标IP或主机名的文件
- `-m, --min-ttl` - 最小TTL值（默认：1）
- `-M, --max-ttl` - 最大TTL值（默认：30）
- `-P, --protocol` - 使用的协议（udp, tcp, icmp, all，默认：all）
- `-p, --port` - 目标端口（UDP/TCP，默认：33434）
- `-s, --size` - 数据包大小（默认：60字节）
- `-w, --wait` - 超时时间（默认：2秒）
- `-q, --queries` - 每跳发送的查询数（默认：3）
- `-i, --interval` - 发包间隔（默认：0.05秒）
- `-n, --no-dns` - 不解析IP地址为主机名
- `-o, --output` - JSON输出文件（默认：traceroute_results.json）
- `-r, --raw-output` - 原始文本输出文件（默认：traceroute_raw.txt） 