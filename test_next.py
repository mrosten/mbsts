import requests
import json
import re

def test():
    html = requests.get('https://polymarket.com/event/btc-updown-5m-1772049000').text
    
    # Extract the full NEXT_DATA json object without regex matching values
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
    if not m:
        print("NEXT_DATA not found. (Cloudflare blocked?)")
        
        # fallback to finding the exact dict via regex if cloudflare blocks script
        return
        
    try:
        data = json.loads(m.group(1))
        # navigate the NextJS tree (usually data.props.pageProps.dehydratedState.queries)
        queries = data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        for q in queries:
            query_key = q.get('queryKey', [])
            if len(query_key) > 1 and query_key[0] == '/api/series' and 'btc-up-or-down-5m' in query_key[1]:
                # Found the series data
                series_data = q.get('state', {}).get('data', [])
                print(f"Found {len(series_data)} series data points.")
                for pt in series_data:
                    if pt.get('endTime') == '2026-02-25T19:50:00.000Z':
                        print("Found the target boundary point!")
                        print(json.dumps(pt, indent=2))
                        return
        print("Object not found in NextJS queries.")
    except Exception as e:
        print(f"Error parsing JSON: {e}")

if __name__ == '__main__':
    test()
