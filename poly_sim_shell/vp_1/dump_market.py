import requests
import json
import time

def dump_market():
    now = int(time.time())
    # Window from ~20 minutes ago
    ts = (now // 300 - 4) * 300
    slug = f"btc-updown-5m-{ts}"
    url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
    
    try:
        r = requests.get(url, timeout=5)
        print(f"Slug: {slug}")
        print(json.dumps(r.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    dump_market()
