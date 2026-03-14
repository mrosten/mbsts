import requests
import json

def debug_p2b(slug):
    url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
    print(f"Fetching: {url}")
    try:
        r = requests.get(url, timeout=5)
        m = r.json()
        
        # Current logic in market.py
        p2b = m.get("priceToBeat")
        found_at = "root"
        
        if p2b is None and m.get("events"):
            evt = m["events"][0]
            if "eventMetadata" in evt:
                p2b = evt["eventMetadata"].get("priceToBeat")
                found_at = "events[0].eventMetadata"
        
        print(f"Result for {slug}:")
        print(f"  p2b: {p2b}")
        print(f"  found_at: {found_at}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test with the slug from the user's screenshot
    debug_p2b("btc-updown-5m-1773305100")
