import requests
import json

slug = "btc-updown-5m-1773225900"
url = f"https://gamma-api.polymarket.com/events?slug={slug}"

try:
    resp = requests.get(url)
    data = resp.json()
    if isinstance(data, list) and len(data) > 0:
        event = data[0]
        markets = event.get('markets', [])
        for m in markets:
            print(f"--- Market ---")
            print(f"Question: {m.get('question')}")
            print(f"Outcome: {m.get('outcome')}")
            print(f"Winner: {m.get('winner')}")
            print(f"Resolved: {m.get('resolved')}")
            print(f"Status: {m.get('status')}")
            # Check market tokens for price 1.0
            tokens = m.get('clobTokenIds', [])
            print(f"Tokens: {tokens}")
    else:
        print(f"No event found for slug: {slug}")
except Exception as e:
    print(f"Error: {e}")
