import requests
import json

def find_active_bitcoin_markets():
    # Broaden search to all active markets
    url = "https://gamma-api.polymarket.com/markets?active=true&limit=100&get_all=true"
    
    try:
        resp = requests.get(url)
        data = resp.json()
        if isinstance(data, list):
            print(f"{'Question':<70} | {'Slug':<40}")
            print("-" * 115)
            for m in data:
                q = m.get('question', '')
                if "Bitcoin" in q:
                    slug = m.get('slug')
                    print(f"{q[:70]:<70} | {slug:<40}")
        else:
            print(f"Unexpected data format: {data}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_active_bitcoin_markets()
