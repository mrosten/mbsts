import requests
import json
import time

def find_sequence():
    now = int(time.time())
    # Find a window that started exactly 30 minutes ago to ensure data is settled in API cache
    base_ts = (now // 300 - 6) * 300
    
    print(f"{'Time':<10} | {'Slug':<30} | {'PriceToBeat':<15}")
    print("-" * 60)
    
    p2b_list = []
    
    for i in range(5):
        ts = base_ts + (i * 300)
        slug = f"btc-updown-5m-{ts}"
        # Use market-specific slug endpoint
        url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
        try:
            r = requests.get(url, timeout=3)
            data = r.json()
            # In /markets/slug/, the data is the market object directly, not a list
            if 'id' in data:
                # The Gamma market object often has groupItemTitle or question
                q = data.get('question', '')
                p2b = data.get('priceToBeat')
                p2b_list.append((ts, slug, p2b))
                print(f"{time.strftime('%H:%M', time.localtime(ts)):<10} | {slug:<30} | {p2b}")
            else:
                print(f"{time.strftime('%H:%M', time.localtime(ts)):<10} | {slug:<30} | NOT FOUND")
        except:
            print(f"{time.strftime('%H:%M', time.localtime(ts)):<10} | {slug:<30} | ERROR")

    print("\nTransition Analysis:")
    for i in range(len(p2b_list)-1):
        ts1, s1, p1 = p2b_list[i]
        ts2, s2, p2 = p2b_list[i+1]
        
        if p1 and p2:
            print(f"Market {s1} settled at close price: {p2}")
            # Note: The 'outcome' of S1 should be determined by comparing its priceToBeat (p1) to p2.
            res = "UP" if float(p2) >= float(p1) else "DOWN"
            print(f"  Result: {res} (Close {p2} vs Open {p1})")

if __name__ == "__main__":
    find_sequence()
