import requests
import time
from datetime import datetime

def poll_next_market():
    # Next 5 min boundary
    now = int(time.time())
    next_ts = (now // 300 + 1) * 300
    slug = f"btc-updown-5m-{next_ts}"
    url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
    
    print(f"Polling for {slug} (Starts at {datetime.fromtimestamp(next_ts).strftime('%H:%M:%S')})")
    print(f"Current Time: {datetime.now().strftime('%H:%M:%S')}")
    
    start_time = time.time()
    # Check for up to 10 minutes (to see when it appears relative to start)
    while time.time() - start_time < 600:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                data = r.json()
                p2b = data.get('priceToBeat')
                if p2b:
                    print(f"\nFOUND! {slug}")
                    print(f"  Appeared at: {datetime.now().strftime('%H:%M:%S')}")
                    print(f"  PriceToBeat: {p2b}")
                    # Also check question for visual confirmation
                    print(f"  Question: {data.get('question')}")
                    return
            elif r.status_code == 404:
                # Still not created
                pass
            else:
                print(f"Unexpected Status: {r.status_code}")
        except:
            pass
        
        time.sleep(1) # Check every second
        
    print("Market never appeared in 10 minutes.")

if __name__ == "__main__":
    poll_next_market()
