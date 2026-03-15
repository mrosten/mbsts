"""
Polymarket Price to Beat Extractor
==================================
Purpose: Extract the "Price to beat" value from Polymarket BTC 5-minute markets
Created: 2026-03-12
Version: 1.0

This module provides functions to scrape the price to beat from Polymarket webpages
when the API doesn't provide this field.
"""

import time
import requests
import json
import re
from datetime import datetime

def get_price_to_beat(window_timestamp=None):
    """
    Extract the price to beat for a specific BTC 5-minute window.
    
    Args:
        window_timestamp (int, optional): Unix timestamp for the window start.
                                        If None, uses current window.
    
    Returns:
        dict: {
            'price_to_beat': float or None,
            'window_start': int,
            'window_slug': str,
            'source': str,
            'error': str or None
        }
    """
    if window_timestamp is None:
        current_ts = int(time.time())
        window_start = current_ts // 300 * 300
    else:
        window_start = window_timestamp
    
    window_slug = f"btc-updown-5m-{window_start}"
    
    result = {
        'price_to_beat': None,
        'window_start': window_start,
        'window_slug': window_slug,
        'source': 'webpage',
        'error': None
    }
    
    try:
        market_url = f'https://polymarket.com/market/{window_slug}'
        
        # Add headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        response = requests.get(market_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            result['error'] = f'HTTP {response.status_code}'
            return result
        
        html_content = response.text
        
        # Primary pattern: priceToBeat as a number
        pattern = r'"priceToBeat"\s*:\s*([0-9,]+\.?\d*)'
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        
        if matches:
            try:
                price_to_beat = float(matches[0].replace(',', ''))
                result['price_to_beat'] = price_to_beat
                return result
            except ValueError:
                pass
        
        # Fallback: Look in __NEXT_DATA__ JSON
        next_data_pattern = r'__NEXT_DATA__[^>]*>([^<]+)</script>'
        json_matches = re.findall(next_data_pattern, html_content)
        
        for json_match in json_matches:
            try:
                json_data = json.loads(json_match)
                json_str = json.dumps(json_data)
                
                # Search for priceToBeat in the JSON
                p2b_match = re.search(r'"priceToBeat"\s*:\s*"([^"]+)"', json_str)
                if p2b_match:
                    price_to_beat = float(p2b_match.group(1).replace(',', ''))
                    result['price_to_beat'] = price_to_beat
                    result['source'] = 'next_data_json'
                    return result
                    
            except (json.JSONDecodeError, ValueError):
                continue
        
        result['error'] = 'Price to beat not found in webpage'
        
    except requests.RequestException as e:
        result['error'] = f'Request failed: {str(e)}'
    except Exception as e:
        result['error'] = f'Unexpected error: {str(e)}'
    
    return result

def get_current_price_to_beat():
    """Get price to beat for the current active window."""
    return get_price_to_beat()

if __name__ == "__main__":
    # Test the function
    print("Testing Price to Beat Extractor")
    print("=" * 40)
    
    result = get_current_price_to_beat()
    
    print(f"Window: {result['window_slug']}")
    print(f"Window Start: {datetime.fromtimestamp(result['window_start']).strftime('%Y-%m-%d %H:%M:%S')}")
    
    if result['price_to_beat']:
        print(f"Price to Beat: ${result['price_to_beat']:,.2f}")
        print(f"Source: {result['source']}")
    else:
        print(f"Error: {result['error']}")
