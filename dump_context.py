import sys
import requests
import re

def test(url):
    html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
    matches = re.finditer(r'.{0,300}\"openPrice\"[ \t]*:[ \t]*[0-9.]+.{0,300}', html)
    for i, m in enumerate(matches):
        print(f"--- MATCH {i} ---")
        print(m.group(0))

if __name__ == '__main__':
    test(sys.argv[1])
