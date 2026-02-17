"""
Fetch Active Token IDs for BTC 15m Markets
useful for manual trading scripts.
"""
import requests
import json
import time
from datetime import datetime, timezone

def fetch_active_markets():
    print("=" * 60)
    print("  FETCHING ACTIVE BTC 15m MARKETS")
    print("=" * 60)

    # 1. Fetch from Gamma API (closed=false)
    # Search for "15m" specifically
    url = "https://gamma-api.polymarket.com/events"
    params = {
        "slug": "15m", # Searching slug usually returns matches
        "closed": "false",
        "limit": 20
    }
    
    try:
        # Also try searching by "tag" or just generic "events"
        # The best way to get active markets is likely /markets with open interests
        # But let's try searching specifically for "Bitcoin" and "15m"
        
        # Searching via `q` (query) is better if supported, but Gamma uses `slug` or `id`
        # Let's try iterating recent events
        resp = requests.get(url, params=params)
        data = resp.json()
        
        if not isinstance(data, list):
            data = []
            
        found_any = False
        current_ts = int(time.time())
        
        print(f"  Scanning {len(data)} events for active BTC 15m markets...")
        
        for event in data:
            title = event.get("title", "")
            slug = event.get("slug", "")
            
            # Filter for BTC 15m
            if "btc" not in title.lower() and "bitcoin" not in title.lower():
                continue
            if "15m" not in title.lower():
                continue
                
            markets = event.get("markets", [])
            for market in markets:
                if "clobTokenIds" not in market:
                    continue
                    
                # Check outcome prices or just list them
                q_title = market.get("question", title)
                
                # Check closed status
                if market.get("closed"):
                    continue
                    
                # Parse Token IDs
                try:
                    token_ids = json.loads(market.get("clobTokenIds", "[]"))
                    outcomes = json.loads(market.get("outcomes", "[]"))
                except:
                    continue
                
                print(f"\nMARKET: {q_title}")
                print(f"  Slug: {slug}")
                
                for i, out in enumerate(outcomes):
                    if i < len(token_ids):
                        print(f"    [{out.upper()}] Token ID: {token_ids[i]}")
                        
                found_any = True

        if not found_any:
            print("\n  [INFO] No specific '15m' markets found via simple search.")
            print("  Listing *any* open Bitcoin market instead...")
            # Fallback search
            resp = requests.get("https://gamma-api.polymarket.com/events", params={"slug": "bitcoin", "closed": "false", "limit": 5})
            data = resp.json()
            for event in data:
                print(f"  - {event.get('title')}")

    except Exception as e:
        print(f"\n  [ERROR] Failed to fetch markets: {e}")
            
    except Exception as e:
        print(f"\n  [ERROR] Failed to fetch markets: {e}")

if __name__ == "__main__":
    fetch_active_markets()
    input("\nPress Enter to exit...")
