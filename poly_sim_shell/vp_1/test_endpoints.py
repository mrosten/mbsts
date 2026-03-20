import requests
import json
import time
from datetime import datetime

def test_endpoints():
    # Let's try to find a market that is definitely old (e.g., 4 hours ago)
    # Current time is ~15:20. 4 hours ago is ~11:20.
    now = int(time.time())
    four_hours_ago = (now // 300 - 48) * 300 
    
    slugs = [
        f"btc-updown-5m-{four_hours_ago}",
        f"btc-updown-5m-{four_hours_ago - 300}",
        f"btc-updown-5m-{four_hours_ago - 600}"
    ]
    
    for slug in slugs:
        print(f"\n--- Testing Slug: {slug} ---")
        
        # Endpoint 1: Markets by Slug
        url_m = f"https://gamma-api.polymarket.com/markets?slug={slug}"
        # Endpoint 2: Events by Slug
        url_e = f"https://gamma-api.polymarket.com/events?slug={slug}"
        
        try:
            r_m = requests.get(url_m)
            m_data = r_m.json()
            if isinstance(m_data, list) and len(m_data) > 0:
                m = m_data[0]
                print(f"  [Market API] Status: {m.get('status')} | Outcome: {m.get('outcome')} | Resolved: {m.get('resolved')}")
            else:
                print(f"  [Market API] No data.")
                
            r_e = requests.get(url_e)
            e_data = r_e.json()
            if isinstance(e_data, list) and len(e_data) > 0:
                e = e_data[0]
                # Check for clobTokenIds or resolution info
                markets = e.get('markets', [])
                if markets:
                    m0 = markets[0]
                    print(f"  [Event API] Status: {m0.get('status')} | Outcome: {m0.get('outcome')} | Resolved: {m0.get('resolved')}")
            else:
                print(f"  [Event API] No data.")
        except Exception as err:
            print(f"  Error: {err}")

if __name__ == "__main__":
    test_endpoints()
