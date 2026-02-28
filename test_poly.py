import requests
import re
import sys

def test(url):
    html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
    matches = re.findall(r'"openPrice":([0-9.]+)', html)
    print(f"Matches for openPrice in HTML: {matches}")
    
    # Also check Next.js data
    m = re.search(r'69142.74', html)
    if m:
        print("Found the exact price string in the HTML!")
    else:
        print("Did not find the exact price string in the HTML.")

if __name__ == '__main__':
    test(sys.argv[1])
