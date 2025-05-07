#!/usr/bin/env python3
# python/handler.py - 接收语音识别的域名并执行traceroute

import os
import sys
import argparse
import importlib.util
from pathlib import Path

# 将当前目录添加到sys.path，以便导入其他模块
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# 导入Traceroute_Demo目录中的Handler模块和Traceroute类
try:
    from Traceroute_Demo.Handler import TracerouteHandler
except ImportError:
    print("无法导入TracerouteHandler类，请确保Traceroute_Demo/Handler.py文件存在")
    sys.exit(1)

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="执行traceroute并生成JSON文件")
    parser.add_argument("domain", help="要traceroute的域名或IP地址")
    args = parser.parse_args()
    
    target_domain = args.domain
    
    print(f"接收到目标域名: {target_domain}")
    
    # 创建TracerouteHandler实例
    output_dir = os.path.join(project_root, "Traceroute_Demo", "traceroute_results")
    os.makedirs(output_dir, exist_ok=True)
    
    handler = TracerouteHandler(output_dir=output_dir)
    
    # traceroute选项
    options = {
        "protocol": "tcp",  # 使用ICMP探测
        "queries": 3,        # 每跳发送3个探测包
        "max_hops": 30,      # 最大跳数
        "wait": 3000,        # 等待时间(ms)
        "no_resolve": False, # 解析主机名
        "extensions": False  # 记录扩展信息
    }
    
    try:
        # 方法1: 直接处理单个目标
        print(f"开始traceroute到: {target_domain}")
        results = handler.process_target(target_domain, options)
        handler.save_results(target_domain, results, "json")
        print(f"Traceroute完成，结果已保存到: {output_dir}")
        
        # 方法2（备选）：使用batch_trace
        # 创建临时文件
        # temp_file = os.path.join(project_root, "python", "temp_target.txt")
        # with open(temp_file, 'w') as f:
        #     f.write(target_domain)
        # print(f"创建临时目标文件: {temp_file}")
        # 
        # # 使用batch_trace处理
        # handler.batch_trace(temp_file, options)
        # 
        # # 清理临时文件
        # os.remove(temp_file)
        
        return 0  # 成功退出码
    except Exception as e:
        print(f"执行traceroute时出错: {e}")
        return 1  # 错误退出码

if __name__ == "__main__":
    sys.exit(main()) 