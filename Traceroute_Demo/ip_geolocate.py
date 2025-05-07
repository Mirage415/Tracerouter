import requests
import csv
import os
import json
import argparse
from typing import Dict, Any
'''
将从traceroute json文件中提取每个跳的IP，
并使用ip-api.com查询其地理位置（经纬度），
然后将结果存储为简单的CSV格式：ip,latitude,longitude
'''

def ip_to_geolocation_data(ip: str) -> Dict[str, Any]:
    """查询IP的地理位置信息（经纬度）"""
    url = f"http://ip-api.com/json/{ip}"
    params = {
        "fields": "status,message,lat,lon,query"  # query是输入的IP
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            # 对于私有IP或查询失败的情况，返回0,0作为坐标
            print(f"IP {ip} 无法定位: {data.get('message', '未知错误')}")
            return {"lat": 0.0, "lon": 0.0, "query": ip}
        return data  # 包含lat, lon, query(IP)
    except Exception as e:
        print(f"查询IP {ip} 地理位置时出错: {e}")
        return {"lat": 0.0, "lon": 0.0, "query": ip}

def process_traceroute_json(json_file_path: str, csv_writer) -> None:
    """处理traceroute JSON文件，提取IP并查询地理位置"""
    if not os.path.exists(json_file_path):
        print(f"JSON文件未找到: {json_file_path}")
        return

    print(f"正在处理JSON文件: {json_file_path}")
    with open(json_file_path, 'r') as f:
        traceroute_data = json.load(f)

    # 收集所有跳数的IP（使用集合去重）
    all_ips = set()
    
    # 提取所有跳数中的IP地址
    for key in traceroute_data:
        if key.isdigit():  # 只处理跳数键
            hop_data = traceroute_data[key]
            for protocol in ["udp", "tcp", "icmp"]:
                if protocol in hop_data and "probes" in hop_data[protocol]:
                    for probe in hop_data[protocol]["probes"]:
                        ip_address = probe.get("from")
                        if ip_address:
                            all_ips.add(ip_address)
    
    # 为每个唯一的IP地址获取地理位置并写入CSV
    for ip in all_ips:
        print(f"查询IP: {ip}")
        geo_data = ip_to_geolocation_data(ip)
        lat = geo_data.get("lat", 0.0)
        lon = geo_data.get("lon", 0.0)
        
        # 只写入IP和经纬度
        csv_writer.writerow([ip, lat, lon])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="从traceroute JSON提取IP并查询地理位置")
    parser.add_argument("domain_name", help="用于识别traceroute JSON文件的域名")
    args = parser.parse_args()

    # 处理域名：将点替换为下划线，以符合文件命名格式
    formatted_domain = args.domain_name.replace('.', '_')
    
    # JSON文件路径 
    json_file_name = f"traceroute_{formatted_domain}.json"
    json_file_path = os.path.join("Traceroute_Demo", "traceroute_results", json_file_name)
    
    # 输出CSV路径
    output_csv_path = os.path.join("renderer", "output.csv")

    try:
        # 确保renderer目录存在
        renderer_dir = os.path.dirname(output_csv_path)
        if renderer_dir and not os.path.exists(renderer_dir):
            os.makedirs(renderer_dir)
            print(f"创建目录: {renderer_dir}")

        # 写入CSV (使用w模式覆盖文件)
        with open(output_csv_path, "w", newline="", encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # 只包含三列：ip,latitude,longitude
            writer.writerow(["ip", "latitude", "longitude"])
            process_traceroute_json(json_file_path, writer)
        
        print(f"地理位置数据已写入: {output_csv_path}")
        exit(0)  # 成功退出
    except Exception as e:
        print(f"处理过程中出错: {e}")
        exit(1)  # 错误退出