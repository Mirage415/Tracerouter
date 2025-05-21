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
    """处理traceroute JSON文件，提取每个协议下每个探针的详细信息（包括地理位置）并写入CSV"""
    if not os.path.exists(json_file_path):
        print(f"JSON文件未找到: {json_file_path}")
        # 写入一个最小化的表头，即使文件未找到或为空
        csv_writer.writerow(["hop", "protocol", "probe_index", "ip", "latitude", "longitude", "message"])
        csv_writer.writerow(["", "", "", "", "", "", f"JSON file not found: {json_file_path}"])
        return

    print(f"正在处理JSON文件: {json_file_path}")
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            traceroute_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"解析JSON文件 {json_file_path} 时出错: {e}")
        csv_writer.writerow(["hop", "protocol", "probe_index", "ip", "latitude", "longitude", "message"])
        csv_writer.writerow(["", "", "", "", "", "", f"Error decoding JSON file: {json_file_path}"])
        return

    all_probe_records = []
    ip_geocache = {}

    # 提取所有跳数中每个协议下每个探针的信息
    for hop_key_str, hop_value in traceroute_data.items():
        if not hop_key_str.isdigit():  # 跳过非跳数键，如 "metadata"
            continue

        hop_number = hop_key_str # 或者 int(hop_key_str)

        for protocol_name, protocol_data in hop_value.items():
            if protocol_name in ["udp", "tcp", "icmp"] and "probes" in protocol_data:
                # 获取当前协议的统计信息
                protocol_stats = protocol_data.get("stats", {})

                for probe_index, probe in enumerate(protocol_data["probes"]):
                    ip_address = probe.get("from")
                    
                    current_probe_record = probe.copy() # Start with all data from the probe
                    current_probe_record["hop"] = hop_number
                    current_probe_record["protocol"] = protocol_name
                    current_probe_record["probe_index"] = probe_index
                    current_probe_record["ip"] = ip_address # Ensure 'ip' field exists even if 'from' is None

                    # 添加协议统计信息，并加上前缀'stats_'
                    for stat_key, stat_value in protocol_stats.items():
                        current_probe_record[f"stats_{stat_key}"] = stat_value

                    if ip_address:
                        if ip_address not in ip_geocache:
                            geo_api_data = ip_to_geolocation_data(ip_address)
                            lat = geo_api_data.get("lat", 0.0)
                            lat = 31.15073 if lat == 0.0 else lat # Default lat
                            lon = geo_api_data.get("lon", 0.0)
                            lon = 121.47711 if lon == 0.0 else lon # Default lon
                            ip_geocache[ip_address] = {"latitude": lat, "longitude": lon}
                        
                        geo_info = ip_geocache[ip_address]
                        current_probe_record["latitude"] = geo_info["latitude"]
                        current_probe_record["longitude"] = geo_info["longitude"]
                    else:
                        # 如果探针没有'from'IP地址，也设置默认/空地理位置信息
                        current_probe_record["latitude"] = 31.15073 # Default lat
                        current_probe_record["longitude"] = 121.47711 # Default lon
                    
                    all_probe_records.append(current_probe_record)
    
    # 定义标准表头顺序
    std_headers = ["hop", "protocol", "probe_index", "ip", "latitude", "longitude"]

    if not all_probe_records:
        print(f"在 {json_file_path} 中没有处理任何探针信息。")
        # 即使没有数据，也写入标准表头
        csv_writer.writerow(std_headers)
        return

    # 确定所有唯一的键名作为CSV表头
    all_keys = set()
    for record in all_probe_records:
        all_keys.update(record.keys())
    
    # 将标准表头放在前面，其余按字母排序
    # 从all_keys中移除std_headers中已有的，避免重复，然后排序
    other_fields = sorted(list(all_keys - set(std_headers)))
    final_headers = std_headers + other_fields
    
    csv_writer.writerow(final_headers)

    # 写入数据行
    for record in all_probe_records:
        # 对于每一行，确保final_headers中的每个列都有值，如果record中没有，则填空字符串
        row = [record.get(header, "") for header in final_headers]
        csv_writer.writerow(row)


if __name__ == '__main__':
    # 如果输入文件
    domain_list = None

    with open("../filename.txt", 'r', encoding='utf-8') as file:
        filepath = file.readline().strip() # file given by Spathis
        print(filepath)

    file = open(filepath, 'r', encoding='utf-8')
    domain_list = [ l.strip() for l in file.readlines() ]
    file.close()

    if domain_list is not None:      # 如果输入的是一个文件路径, 即包含所有目标ip的文件。则输出每一个ip对应的traceroute结果文件
        for domain_name in domain_list:
            formatted_domain = domain_name.replace('.', '_').strip()
            
                # JSON文件路径
            json_file_name = f"traceroute_{formatted_domain}.json"
            json_file_path = os.path.join("traceroute_results", json_file_name)
            print(json_file_path)
            
            # 输出CSV路径
            output_csv_path = os.path.join("..","renderer", f"output_{formatted_domain}.csv")

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
                    # writer.writerow(["ip", "latitude", "longitude"])
                    process_traceroute_json(json_file_path, writer)
                

            except Exception as e:
                print(f"处理过程中出错: {e}")
                exit(1)  # 错误退出

    else:                           # 如果输入的是单个网址
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
                # writer.writerow(["ip", "latitude", "longitude"])
                process_traceroute_json(json_file_path, writer)
            
            print(f"地理位置数据已写入: {output_csv_path}")
            exit(0)  # 成功退出
        except Exception as e:
            print(f"处理过程中出错: {e}")
            exit(1)  # 错误退出
    exit(0)  # 成功退出
