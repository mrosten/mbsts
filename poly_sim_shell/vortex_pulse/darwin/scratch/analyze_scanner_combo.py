import json

def analyze_data(data):
    scanner_combo = ['Nitro', 'VolSnap', 'WCP']
    combo_counts = {"UP": 0, "DOWN": 0, "TOTAL": 0}
    for window in data:
        if 'scanners_fired' in window and all(scanner in window['scanners_fired'] for scanner in scanner_combo):
            combo_counts['TOTAL'] += 1
            if window['winner'] == 'UP':
                combo_counts['UP'] += 1
            elif window['winner'] == 'DOWN':
                combo_counts['DOWN'] += 1

    return combo_counts


filename = 'memory.json'

try:
    with open(filename, 'r') as f:
        memory = json.load(f)

    analysis_results = analyze_data(memory)

    print(json.dumps(analysis_results))

except FileNotFoundError:
    print(json.dumps({"error": "Memory file not found"}))
except json.JSONDecodeError:
    print(json.dumps({"error": "Invalid JSON format in memory file"}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
