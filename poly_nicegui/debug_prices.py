import requests
import json

# URL from user logs (might be expired but structure remains)
slug = "btc-updown-15m-1769434200" 
url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"

print(f"Fetching: {url}")
try:
    resp = requests.get(url)
    data = resp.json()
    
    print("\n--- RAW DATA ---")
    outcomes_str = data.get("outcomes")
    prices_str = data.get("outcomePrices")
    
    print(f"Outcomes (Raw): {outcomes_str} (Type: {type(outcomes_str)})")
    print(f"Prices   (Raw): {prices_str} (Type: {type(prices_str)})")
    
    if outcomes_str:
        outcomes = json.loads(outcomes_str)
        prices = json.loads(prices_str)
        
        print(f"\nparsed outcomes: {outcomes}")
        print(f"parsed prices:   {prices}")
        
        up_idx, down_idx = 0, 1
        for i, name in enumerate(outcomes):
            if str(name).lower() in ["up", "yes", "higher"]: up_idx = i
            if str(name).lower() in ["down", "no", "lower"]: down_idx = i
            
        print(f"\nCalculated Indices: UP={up_idx}, DOWN={down_idx}")
        print(f"UP Price:   {prices[up_idx]}")
        print(f"DOWN Price: {prices[down_idx]}")
        
except Exception as e:
    print(f"Error: {e}")
