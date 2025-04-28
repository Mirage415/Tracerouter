import requests 

def ip_to_lattitude_longitutde(ip: str) -> tuple[float, float]:
    # A geo ip function that returns latitude and longitude) 
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