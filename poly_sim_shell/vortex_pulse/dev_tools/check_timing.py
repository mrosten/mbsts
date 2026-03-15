import requests
import time
from datetime import datetime

def check_timing():
    # current time is 00:21:04.
    # We want to see if the 00:25:00 market exists.
    now = int(time.time())
    # 00:25:00 TS
    target_ts = (now // 300 + 1) * 300
    slug = f"btc-updown-5m-{target_ts}"
    url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
    
    print(f"Target: {slug} (Starts at {datetime.fromtimestamp(target_ts).strftime('%H:%M:%S')})")
    
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            p2b = data.get('priceToBeat')
            print(f"STATUS: FOUND")
            print(f"PriceToBeat: {p2b}")
        else:
            print(f"STATUS: NOT FOUND (HTTP {r.status_code})")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_timing()
