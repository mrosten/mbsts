import requests
import json
import time

def find_resolved_markets():
    # Get all markets for the BTC Up/Down event group
    # We'll use a search query for 'Bitcoin Up or Down' 
    url = "https://gamma-api.polymarket.com/markets?active=false&limit=50&order=closed_time&ascending=false&get_all=true"
    
    print(f"Scanning for resolved BTC 5m markets...")
    try:
        resp = requests.get(url)
        data = resp.json()
        if isinstance(data, list):
            found = 0
            for m in data:
                q = m.get('question', '')
                if "Bitcoin Up or Down" in q and "5 Minutes" in q:
                    status = m.get('status')
                    outcome = m.get('outcome')
                    resolved = m.get('resolved')
                    
                    if outcome or resolved:
                        print(f"\n✅ RESOLVED: {q}")
                        print(f"  Slug: {m.get('slug')}")
                        print(f"  Status: {status}")
                        print(f"  Outcome: {outcome}")
                        print(f"  Resolved: {resolved}")
                        print(f"  Closed Time: {m.get('closedTime')}")
                        found += 1
            
            if found == 0:
                print("No explicitly resolved 5m markets found in the last 50 inactive markets.")
        else:
            print(f"Unexpected data format: {data}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_resolved_markets()
