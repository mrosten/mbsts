import requests
from datetime import datetime, timezone
import re

url = "https://polymarket.com/event/btc-updown-5m-1772049300"
slug = "btc-updown-5m-1772049300"
api_url = f"https://gamma-api.polymarket.com/events?slug={slug}"

r = requests.get(api_url).json()
start_time_str = r[0]['markets'][0]['eventStartTime']
print(f"API Start Time: {start_time_str}")

html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
start_time_iso = start_time_str.replace('Z', '+00:00')
start_dt = datetime.fromisoformat(start_time_iso)
now_dt = datetime.now(timezone.utc)
if now_dt < start_dt:
    print("Window not active yet")

if not start_time_str.endswith('.000Z'):
    target_time_js = start_time_str.replace('Z', '.000Z')
else:
    target_time_js = start_time_str

print(f"Target JS time: {target_time_js}")

pat = r'"endTime"\s*:\s*"{}"[^{{}}]+"closePrice"\s*:\s*([^,}}]+)'.format(target_time_js.replace('.', r'\.'))
print(f"Regex pattern: {pat}")
m = re.search(pat, html)
if m:
    print(f"Match found! closePrice is: {m.group(1)}")
else:
    print("Match NOT found.")
    
# dump all endtimes/closeprices
all_matches = re.finditer(r'"endTime"\s*:\s*"([^"]+)"[^{}]+"closePrice"\s*:\s*([^,}]+)', html)
print("\nAll endTime/closePrice pairs in HTML:")
for m2 in list(all_matches)[-5:]:
    print(m2.group(1), m2.group(2))
