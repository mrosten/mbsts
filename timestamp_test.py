import re

def parse():
    html = open('live_raw.html', 'r', encoding='utf-8').read()
    
    # We pretend our eventStartTime is 19:40:00Z
    target_time = "2026-02-25T19:40:00.000Z"
    
    # Look for the series object where endTime matches our target start time
    pat = r'"endTime":"{}"[^{{}}]+"closePrice":([^,}}]+)'.format(target_time)
    
    m = re.search(pat, html)
    if m:
        print(f"Matched closePrice of preceding window: {m.group(1)}")
    else:
        print("No match found for pattern:", pat)
        
if __name__ == '__main__':
    parse()
