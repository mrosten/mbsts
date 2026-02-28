import sys
import requests
import re
import json
from datetime import datetime, timezone

def get_poly_open(url):
    # Extract the slug from the URL.
    match = re.search(r'polymarket\.com/event/([^/?#]+)', url)
    if not match:
        print("Error: Could not extract event slug from the URL.")
        return
        
    slug = match.group(1)
    api_url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    
    try:
        response = requests.get(api_url, timeout=10)
        data = response.json()
        
        if not data or not isinstance(data, list) or len(data) == 0:
            print(f"Error: Event not found for slug '{slug}'.")
            return
            
        event = data[0]
        
        start_time_str = None
        markets = event.get('markets', [])
        if markets and len(markets) > 0:
            start_time_str = markets[0].get('eventStartTime')
            
            if start_time_str:
                start_time_iso = start_time_str.replace('Z', '+00:00')
                start_dt = datetime.fromisoformat(start_time_iso)
                now_dt = datetime.now(timezone.utc)
                
                if now_dt < start_dt:
                    print("Window is not active yet.")
                    return
        
        # 1. Attempt to get it from the API directly (works for older closed windows)
        meta = event.get('eventMetadata', {})
        if meta and 'priceToBeat' in meta:
            price_to_beat = meta.get('priceToBeat')
            try:
                val = float(price_to_beat)
                print(f"Opening Price to Beat: ${val:,.2f}")
                return
            except ValueError:
                print(f"Opening Price to Beat: {price_to_beat}")
                return

        # 2. Fallback to scraping the HTML (required for active live windows)
        if not start_time_str:
            print("Error: Window lacks an eventStartTime to correlate Oracle pricing.")
            return
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        html_response = requests.get(url, headers=headers, timeout=10)
        html = html_response.text
        
        # Strategy: Polymarket's series array strings continuous windows together.
        # The start time of the current window equals the 'endTime' of the PREVIOUS window object in Next.js.
        # The 'closePrice' of that PREVIOUS window is identical to the 'openPrice' of the CURRENT window.
        # If the Chainlink Oracle hasn't published the price yet (e.g. first 55 seconds), 'closePrice' is `null`.
        
        # We search specifically for the object representing the boundary: endTime = our eventStartTime
        # Format in NextJS: "endTime":"2026-02-25T19:40:00.000Z" (We may need to format it like '.000Z')
        if not start_time_str.endswith('.000Z'):
            target_time_js = start_time_str.replace('Z', '.000Z')
        else:
            target_time_js = start_time_str
            
        pat = r'"endTime"\s*:\s*"{}"[^{{}}]+"closePrice"\s*:\s*([^,}}]+)'.format(target_time_js.replace('.', r'\.'))
        m = re.search(pat, html)
        if m:
            oracle_price = m.group(1).strip()
            
            if oracle_price == "null" or oracle_price == '""':
                print("Window price not settled yet (Waiting for Oracle).")
                return
            else:
                try:
                    val = float(oracle_price)
                    print(f"Opening Price to Beat: ${val:,.2f}")
                    return
                except ValueError:
                    print("Window price not settled yet (Waiting for Oracle).")
                    return
        
        # If we failed to find the exact boundary object, just look for the active window marker as backup
        # The active window block has: `{"openPrice":68878.50,"closePrice":null}` natively.
        # We can find the final openPrice block (with no startTime), meaning it's the active one.
        alt_m = re.search(r'\{[^{}]*"openPrice"\s*:\s*([0-9.]+)[^{}]*"closePrice"\s*:\s*null[^{}]*\}', html)
        if alt_m:
            val = float(alt_m.group(1))
            print(f"Opening Price to Beat: ${val:,.2f}")
            return
            
        # The oracle simply hasn't fed the data layer yet.
        print("Window price not settled yet (Waiting for Oracle).")
            
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching data: {e}")
    except ValueError:
        print("Error: Invalid JSON response from Polymarket API.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python get_poly_open.py <polymarket_event_url>")
    else:
        url = sys.argv[1]
        get_poly_open(url)
