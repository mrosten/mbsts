
import requests
import json
import re
import time

def extract_p2b(slug):
    try:
        # Test both /market/ and /event/ patterns
        urls = [
            f'https://polymarket.com/market/{slug}',
            f'https://polymarket.com/event/{slug}'
        ]
        
        results = {}
        for market_url in urls:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            print(f"Fetching {market_url}...")
            response = requests.get(market_url, headers=headers, timeout=10)
            print(f"Status: {response.status_code}")
            
            html_content = response.text
            
            # Pattern 1
            pattern = r'"priceToBeat"\s*:\s*([0-9,]+\.?\d*)'
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            p1 = float(matches[0].replace(',', '')) if matches else None
            
            # Pattern 2: NEXT_DATA
            p2 = None
            next_data_pattern = r'__NEXT_DATA__[^>]*>([^<]+)</script>'
            json_matches = re.findall(next_data_pattern, html_content)
            for json_match in json_matches:
                try:
                    json_data = json.loads(json_match)
                    json_str = json.dumps(json_data)
                    p2b_match = re.search(r'"priceToBeat"\s*:\s*"?([0-9,]+\.?\d*)"?', json_str)
                    if p2b_match:
                        p2 = float(p2b_match.group(1).replace(',', ''))
                        break
                except: continue
                
            results[market_url] = {"p1": p1, "p2": p2}
        return results
    except Exception as e:
        return f"Error: {e}"

# Test slugs from the logs
test_slugs = [
    "btc-updown-5m-1773343200",
    "btc-updown-5m-1773343500",
    "btc-updown-5m-1773343800"
]

for s in test_slugs:
    print(f"\n--- Testing Slug: {s} ---")
    print(extract_p2b(s))
    time.sleep(1)
