import requests
import json
import re
import sys

def fetch_poly_data(url):
    print(f"Fetching {url}...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    html = requests.get(url, headers=headers).text
    
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not m:
        print("No __NEXT_DATA__ found. Saving raw HTML.")
        with open("raw.html", "w", encoding="utf-8") as f:
            f.write(html)
        return
        
    data = json.loads(m.group(1))
    with open("poly_next_data.json", "w") as f:
        json.dump(data, f, indent=2)
    print("Saved poly_next_data.json")

if __name__ == "__main__":
    fetch_poly_data("https://polymarket.com/event/btc-updown-5m-1772042400")
