import requests
import re
import sys

def parse(url):
    html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
    matches = re.findall(r'"openPrice"\s*:\s*([0-9.]+)', html)
    print("All openPrices found:")
    for i, m in enumerate(matches):
        print(f"[{i}]: {m}")
        
    print("---\nLet's check for proximity to 69142.74")
    # let's grab what's around 69142.74 to see the real structure
    ctx = re.search(r'(.{0,150}69142\.74.{0,150})', html)
    if ctx:
        print("Context around target price:")
        print(ctx.group(1))

if __name__ == '__main__':
    parse(sys.argv[1])
