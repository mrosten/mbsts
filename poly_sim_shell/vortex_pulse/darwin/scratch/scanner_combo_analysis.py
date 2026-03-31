import json

def analyze_scanner_combo(data):
    # This is a simplified analysis, adjust based on data structure
    scanner_combo = ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']
    combo_count = 0
    up_after_combo = 0
    down_after_combo = 0

    for window in data:
        if 'scanners' in window and all(scanner in window['scanners'] for scanner in scanner_combo):
            combo_count += 1
            if 'winner' in window:
                if window['winner'] == 'UP':
                    up_after_combo += 1
                else:
                    down_after_combo += 1

    if combo_count > 0:
        up_pct = up_after_combo / combo_count
        down_pct = down_after_combo / combo_count
        print(f'Scanner combo count: {combo_count}')
        print(f'UP after combo: {up_pct:.2f}')
        print(f'DOWN after combo: {down_pct:.2f}')
        
        # Simple recommendation based on observed probabilities:
        if up_pct > down_pct:
            print('Recommendation: Potential UP move after combo.')
        else:
            print('Recommendation: Potential DOWN move after combo.')
    else:
        print('Scanner combo not found in the data.')

# Example Usage (replace with actual data loading):
# Assuming you have historical data stored in a list of dictionaries:
# historical_data = [...]
# Replace with your data loading mechanism (e.g., reading from a file)

# Example using a very simple hardcoded dataset for demonstration:
historical_data = [
    {'scanners': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT'], 'winner': 'DOWN'},
    {'scanners': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT'], 'winner': 'UP'},
    {'scanners': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT'], 'winner': 'DOWN'},
    {'scanners': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT'], 'winner': 'DOWN'},
    {'scanners': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT'], 'winner': 'UP'},
    {'scanners': ['Nitro', 'VolSnap'], 'winner': 'UP'}
]

analyze_scanner_combo(historical_data)