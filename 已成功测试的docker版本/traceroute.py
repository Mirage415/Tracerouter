#!/usr/bin/env python3
"""
自定义Traceroute工具
根据输入的IP地址列表和选项，使用不同协议（UDP、TCP、ICMP）探测网络路径
"""

import argparse
import csv
import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import dns.resolver
from scapy.all import IP, UDP, TCP, ICMP, sr1, RandShort
from scapy.layers.inet import traceroute
from tqdm import tqdm

# 协议类型枚举
PROTO_UDP = 'udp'
PROTO_TCP = 'tcp'
PROTO_ICMP = 'icmp'
ALL_PROTOCOLS = [PROTO_UDP, PROTO_TCP, PROTO_ICMP]

class CustomTraceRoute:
    def __init__(self, 
                 target_ips=None, 
                 input_file=None,
                 max_ttl=30, 
                 min_ttl=1, 
                 timeout=2, 
                 retry=3,
                 protocols=None, 
                 port=33434, 
                 packet_size=60,
                 interval=0.05,
                 resolve_dns=True,
                 output_file='traceroute_results.json',
                 raw_output_file='traceroute_raw.txt'):
        """
        初始化自定义Traceroute工具
        
        参数:
            target_ips: 目标IP地址列表
            input_file: 包含目标IP的输入文件
            max_ttl: 最大TTL值
            min_ttl: 最小TTL值
            timeout: 超时时间（秒）
            retry: 重试次数
            protocols: 要使用的协议列表 (UDP, TCP, ICMP)
            port: 目标端口 (UDP/TCP)
            packet_size: 数据包大小（字节）
            interval: 发包间隔（秒）
            resolve_dns: 是否解析DNS
            output_file: 输出文件名
            raw_output_file: 原始输出文件名
        """
        self.target_ips = target_ips or []
        self.input_file = input_file
        self.max_ttl = max_ttl
        self.min_ttl = min_ttl
        self.timeout = timeout
        self.retry = retry
        self.protocols = protocols or ALL_PROTOCOLS
        self.port = port
        self.packet_size = packet_size
        self.interval = interval
        self.resolve_dns = resolve_dns
        self.output_file = output_file
        self.raw_output_file = raw_output_file
        self.results = {}
        
        # 如果提供了输入文件，从文件中读取IP地址
        if input_file:
            self._load_ips_from_file()
            
    def _load_ips_from_file(self):
        """从文件加载IP地址"""
        try:
            with open(self.input_file, 'r') as f:
                # 尝试不同的文件格式
                if self.input_file.endswith('.csv'):
                    reader = csv.reader(f)
                    for row in reader:
                        if row and self._is_valid_ip(row[0].strip()):
                            self.target_ips.append(row[0].strip())
                else:  # 假设是txt文件
                    for line in f:
                        ip = line.strip()
                        if self._is_valid_ip(ip):
                            self.target_ips.append(ip)
            print(f"从文件加载了 {len(self.target_ips)} 个IP地址")
        except Exception as e:
            print(f"加载IP地址文件时出错: {e}")
            sys.exit(1)
    
    def _is_valid_ip(self, ip):
        """检查IP地址是否有效"""
        try:
            socket.inet_aton(ip)
            return True
        except:
            return False
            
    def _resolve_hostname(self, ip):
        """解析IP的主机名"""
        if not self.resolve_dns:
            return None
        try:
            return socket.gethostbyaddr(ip)[0]
        except:
            return None
            
    def _send_probe(self, target_ip, ttl, protocol):
        """
        发送探测包并返回结果
        
        参数:
            target_ip: 目标IP
            ttl: TTL值
            protocol: 协议类型 (UDP, TCP, ICMP)
            
        返回:
            字典包含响应IP、RTT等信息
        """
        start_time = time.time()
        
        # 创建基本的IP包
        ip_packet = IP(dst=target_ip, ttl=ttl)
        
        # 根据协议类型添加相应的载荷
        if protocol == PROTO_UDP:
            packet = ip_packet / UDP(dport=self.port, sport=RandShort())
        elif protocol == PROTO_TCP:
            packet = ip_packet / TCP(dport=self.port, sport=RandShort(), flags="S")
        elif protocol == PROTO_ICMP:
            packet = ip_packet / ICMP(type=8, code=0)  # Echo Request
        
        # 如果需要，添加填充以达到指定的数据包大小
        header_size = len(packet)
        if self.packet_size > header_size:
            padding_size = self.packet_size - header_size
            packet = packet / (b'X' * padding_size)
        
        # 发送数据包并等待响应
        reply = sr1(packet, timeout=self.timeout, verbose=0)
        
        end_time = time.time()
        rtt = (end_time - start_time) * 1000  # 转换为毫秒
        
        result = {
            'protocol': protocol,
            'ttl': ttl,
            'rtt': rtt,
            'success': False,
            'resp_ip': None,
            'hostname': None,
            'is_destination': False
        }
        
        if reply is None:
            return result
            
        # 处理响应
        result['success'] = True
        result['resp_ip'] = reply.src
        
        # 检查是否到达目标
        if reply.src == target_ip:
            result['is_destination'] = True
        
        # 如果需要，解析主机名
        if self.resolve_dns:
            result['hostname'] = self._resolve_hostname(reply.src)
            
        return result
        
    def trace_route(self, target_ip):
        """
        对单个目标IP执行Traceroute
        
        参数:
            target_ip: 目标IP地址
            
        返回:
            包含所有跳数和协议结果的字典
        """
        print(f"\n开始对 {target_ip} 进行Traceroute...")
        
        results = {
            'target': target_ip,
            'timestamp': datetime.now().isoformat(),
            'hops': {}
        }
        
        reached_destination = False
        
        # 从最小TTL开始，逐步增加直到最大TTL或到达目标
        for ttl in range(self.min_ttl, self.max_ttl + 1):
            if reached_destination:
                break
                
            hop_results = {}
            
            # 对每个协议进行探测
            for protocol in self.protocols:
                protocol_results = []
                
                # 每个协议重试指定次数
                for attempt in range(self.retry):
                    result = self._send_probe(target_ip, ttl, protocol)
                    protocol_results.append(result)
                    
                    # 检查是否到达目标
                    if result['is_destination']:
                        reached_destination = True
                        
                    # 等待指定的时间间隔
                    if attempt < self.retry - 1:  # 最后一次尝试后不需要等待
                        time.sleep(self.interval)
                
                hop_results[protocol] = protocol_results
            
            # 记录此跳的结果
            results['hops'][str(ttl)] = hop_results
            
            # 在控制台显示结果
            self._print_hop_result(ttl, hop_results)
            
        return results
        
    def _print_hop_result(self, ttl, hop_results):
        """打印单个跳结果"""
        print(f"\n{ttl:2d}", end="  ")
        
        # 收集此跳的所有IP地址
        ips = set()
        for protocol in hop_results:
            for result in hop_results[protocol]:
                if result['success'] and result['resp_ip']:
                    ips.add(result['resp_ip'])
        
        if not ips:
            print("* * *")
            return
            
        # 打印每个IP和RTT
        for ip in ips:
            hostname = None
            rtts = []
            
            # 收集所有协议的RTT值
            for protocol in hop_results:
                for result in hop_results[protocol]:
                    if result['success'] and result['resp_ip'] == ip:
                        rtts.append(f"{result['rtt']:.2f}ms ({protocol})")
                        if result['hostname']:
                            hostname = result['hostname']
            
            ip_str = f"{ip}"
            if hostname:
                ip_str += f" ({hostname})"
                
            print(f"{ip_str:40s}  {' '.join(rtts)}")
    
    def run(self):
        """运行Traceroute对所有目标IP"""
        if not self.target_ips:
            print("错误: 没有提供目标IP地址")
            return
            
        all_results = {}
        
        with open(self.raw_output_file, 'w') as raw_file:
            # 记录开始时间
            raw_file.write(f"Traceroute 开始时间: {datetime.now().isoformat()}\n")
            raw_file.write(f"使用协议: {', '.join(self.protocols)}\n")
            raw_file.write(f"目标IPs: {', '.join(self.target_ips)}\n\n")
            
            # 对每个目标IP执行Traceroute
            for ip in tqdm(self.target_ips, desc="处理目标IP"):
                result = self.trace_route(ip)
                all_results[ip] = result
                
                # 将原始结果写入文本文件
                raw_file.write(f"\n{'='*40}\n")
                raw_file.write(f"目标: {ip}\n")
                raw_file.write(f"时间: {result['timestamp']}\n")
                raw_file.write(f"{'-'*40}\n")
                
                for ttl in result['hops']:
                    raw_file.write(f"TTL: {ttl}\n")
                    
                    hop_results = result['hops'][ttl]
                    for protocol in hop_results:
                        raw_file.write(f"  协议: {protocol}\n")
                        
                        for i, probe_result in enumerate(hop_results[protocol]):
                            if probe_result['success']:
                                raw_file.write(f"    尝试 {i+1}: {probe_result['resp_ip']} - RTT: {probe_result['rtt']:.2f}ms")
                                if probe_result['hostname']:
                                    raw_file.write(f" ({probe_result['hostname']})")
                                raw_file.write("\n")
                            else:
                                raw_file.write(f"    尝试 {i+1}: *\n")
                    
                    raw_file.write("\n")
        
        # 将结果保存为JSON
        with open(self.output_file, 'w') as f:
            json.dump(all_results, f, indent=2)
            
        print(f"\n完成所有Traceroute，结果已保存到 {self.output_file} 和 {self.raw_output_file}")
        return all_results

def main():
    """主函数：解析命令行参数并运行Traceroute"""
    parser = argparse.ArgumentParser(description='自定义Traceroute工具')
    
    # 目标参数
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument('-t', '--target', action='append', help='目标IP地址（可多次指定）')
    target_group.add_argument('-f', '--file', help='包含目标IP的文件（txt或csv格式）')
    
    # TTL参数
    parser.add_argument('-m', '--min-ttl', type=int, default=1, help='最小TTL值（默认：1）')
    parser.add_argument('-M', '--max-ttl', type=int, default=30, help='最大TTL值（默认：30）')
    
    # 协议参数
    parser.add_argument('-P', '--protocol', choices=['udp', 'tcp', 'icmp', 'all'], default='all',
                       help='使用的协议（默认：all）')
    
    # 其他参数
    parser.add_argument('-p', '--port', type=int, default=33434, help='目标端口（UDP/TCP，默认：33434）')
    parser.add_argument('-s', '--size', type=int, default=60, help='数据包大小，单位为字节（默认：60）')
    parser.add_argument('-w', '--wait', type=float, default=2, help='超时时间，单位为秒（默认：2）')
    parser.add_argument('-q', '--queries', type=int, default=3, help='每跳发送的查询数（默认：3）')
    parser.add_argument('-i', '--interval', type=float, default=0.05, help='发包间隔，单位为秒（默认：0.05）')
    parser.add_argument('-n', '--no-dns', action='store_true', help='不解析IP地址为主机名')
    parser.add_argument('-o', '--output', default='traceroute_results.json', help='JSON输出文件（默认：traceroute_results.json）')
    parser.add_argument('-r', '--raw-output', default='traceroute_raw.txt', help='原始文本输出文件（默认：traceroute_raw.txt）')
    
    args = parser.parse_args()
    
    # 处理协议参数
    if args.protocol == 'all':
        protocols = ALL_PROTOCOLS
    else:
        protocols = [args.protocol]
    
    # 创建并运行Traceroute
    tracer = CustomTraceRoute(
        target_ips=args.target,
        input_file=args.file,
        max_ttl=args.max_ttl,
        min_ttl=args.min_ttl,
        timeout=args.wait,
        retry=args.queries,
        protocols=protocols,
        port=args.port,
        packet_size=args.size,
        interval=args.interval,
        resolve_dns=not args.no_dns,
        output_file=args.output,
        raw_output_file=args.raw_output
    )
    
    tracer.run()

if __name__ == "__main__":
    main() 