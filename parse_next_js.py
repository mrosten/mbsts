import json
import re

def analyze():
    try:
        html = open('live_raw.html', 'r', encoding='utf-8').read()
    except:
        html = open('active_market.json', 'r', encoding='utf-8').read() # fallback file if live_raw is gone
        
    print(f"File length: {len(html)}")
    
    # We want to find cases of "slug":"btc-updown-5m-some-time" and see if "openPrice" is near it.
    for match in re.finditer(r'\{[^{}]*"openPrice":[0-9.]+[^{}]*\}', html):
        print("FOUND BLOCK WITH openPrice:")
        print(match.group(0))
        print("---")
        
    for match in re.finditer(r'\"openPrice\"[^\}]+\}', html):
        print("FOUND chunk starting with openPrice:")
        print(match.group(0)[:200])
        print("---")

if __name__ == '__main__':
    analyze()
