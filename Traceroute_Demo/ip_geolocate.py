import requests 
import csv
import os
'''
your-app/
├─ main.js
├─ preload.js
└─ renderer/
   ├─ index.html
   ├─ globe_cesium.js
   ├─ renderer.js
   └─ output.csv      ← Python 每跑一跳追加写入的文件
'''

def ip_to_lattitude_longitutde(ip: str) -> tuple[float, float]:
    # A geo ip function that returns latitude and longitude
    url = f"http://ip-api.com/json/{ip}" 
    params = { 
        "fiels": "status, message, lat, lon"
    }
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Geographic lookup failed: {data.get('message')}")
    return data["lat"], data["lon"]

if __name__ == '__main__':
    test_ip = str(input('input the ip address'))  # 可替换为其他测试IP地址
    try:
        lat, lon = ip_to_lattitude_longitutde(test_ip)
        print(f"IP {test_ip} 位于纬度: {lat}, 经度: {lon}")
        
        csv_file = "renderer/output.csv"
        file_exists = os.path.isfile(csv_file)
        with open(csv_file, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            # 如果文件不存在则写入表头
            if not file_exists:
                writer.writerow(["ip", "latitude", "longitude"])
            writer.writerow([test_ip, lat, lon])
        print(f"经纬度已追加保存至 {csv_file}")
    except Exception as e:
        print(f"错误: {e}")