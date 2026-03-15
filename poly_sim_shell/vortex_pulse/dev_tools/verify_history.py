import requests
from datetime import datetime, timedelta
import time

def get_historical_markets():
    # Attempt to find markets from ~1 and ~2 hours ago
    # Using 5m intervals. Format: btc-updown-5m-TIMESTAMP
    now = int(time.time())
    
    # Round down to nearest 5 min (300s)
    base_ts = (now // 300) * 300
    
    # Let's check 1 hour ago (12 intervals back) and 2 hours ago (24 back)
    target_ts = [
        base_ts - (300 * 12),  # ~60 mins ago
        base_ts - (300 * 13),  # ~65 mins ago
        base_ts - (300 * 24),  # ~120 mins ago
        base_ts - (300 * 25)   # ~125 mins ago
    ]
    
    for ts in target_ts:
        slug = f"btc-updown-5m-{ts}"
        url = f"https://gamma-api.polymarket.com/events?slug={slug}"
        print(f"\n--- Checking {slug} (Window Start: {datetime.fromtimestamp(ts).strftime('%H:%M:%S')}) ---")
        try:
            resp = requests.get(url)
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                event = data[0]
                markets = event.get('markets', [])
                for m in markets:
                    # Final outcome is usually in 'outcome' of the market object 
                    # OR we check which token is priced at 1.0 (though that's for CLOB)
                    print(f"  Market: {m.get('question')}")
                    print(f"  Status: {m.get('status')}")
                    print(f"  Outcome: {m.get('outcome')}")
                    print(f"  Resolved: {m.get('resolved')}")
                    
                    # Also check for definitive resolution data in event level
                    price_to_beat = event.get('priceToBeat')
                    if price_to_beat:
                        print(f"  Price to Beat: {price_to_beat}")
            else:
                print(f"  No event found for {slug}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    get_historical_markets()
