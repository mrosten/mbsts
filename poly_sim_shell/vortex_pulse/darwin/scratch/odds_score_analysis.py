import json

def analyze_data(data):
    up_count = 0
    down_count = 0
    total_windows = 0

    for window_id, window_data in data.items():
        if 'winner' not in window_data:
            continue
        if ('Nitro' in window_data.get('scanners_fired', []) and 'VolSnap' in window_data.get('scanners_fired', []) and window_data.get('1H_Trend') == 'S-DOWN'):
            total_windows += 1
            if window_data.get('Odds_Score', 0) > 50:
                if window_data['winner'] == 'UP':
                    up_count += 1
                else:
                    down_count += 1

    if total_windows > 0:
        up_ratio = up_count / total_windows
        down_ratio = down_count / total_windows
        print(f"Windows with Nitro, VolSnap, S-DOWN, Odds Score > 50: Total={total_windows}, UP={up_count}, DOWN={down_count}, UP Ratio={up_ratio:.2f}, DOWN Ratio={down_ratio:.2f}")
    else:
        print("No relevant windows found.")

# Example usage (replace with actual data retrieval)
data = {
    'btc-updown-5m-1774018500': {'scanners_fired': ['Nitro', 'VolSnap'], '1H_Trend': 'S-DOWN', 'Odds_Score': 60, 'winner': 'UP'},
    'btc-updown-5m-1774033200': {'scanners_fired': ['Nitro', 'VolSnap'], '1H_Trend': 'S-DOWN', 'Odds_Score': 93, 'winner': 'UP'},
    'btc-updown-5m-1774033500': {'scanners_fired': ['Nitro', 'VolSnap'], '1H_Trend': 'S-DOWN', 'Odds_Score': 30, 'winner': 'DOWN'}
}


# Parse the 'YOUR MEMORY' section and transform it into the expected format for analysis.
memory_data = [
  {"Window": "btc-updown-5m-1774018500", "hypothesis": "The firing of 'Nitro' and 'VolSnap' together with a S-DOWN 1H trend is not consistently predicting DOWN moves. The current window resulted in an UP move despite these conditions. I will now investigate if the positive odds score has more predictive power than the 'Nitro' and 'VolSnap' combination.", "signal": "N/A", "winner": "UP", "outcome": "HOLD", "scanners_fired": ["Nitro", "VolSnap"], "1H_Trend": "S-DOWN", "Odds_Score": 93},
  {"Window": "btc-updown-5m-1774033200", "winner": "UP", "scanners_fired": ["Nitro", "VolSnap"], "1H_Trend": "S-DOWN", "Odds_Score": 93}
]

def transform_memory_data(memory_data):
    transformed_data = {}
    for item in memory_data:
      window_id = item.get('Window')
      if window_id:
        transformed_data[window_id] = {
            'scanners_fired': item.get('scanners_fired', []),
            '1H_Trend': item.get('1H_Trend'),
            'Odds_Score': item.get('Odds_Score'),
            'winner': item.get('winner', 'N/A') # Handle windows without a 'winner'
        }
    return transformed_data

#Transform the memory data
transformed_memory_data = transform_memory_data([
  {"Window": "btc-updown-5m-1774018500", "hypothesis": "The firing of 'Nitro' and 'VolSnap' together with a S-DOWN 1H trend is not consistently predicting DOWN moves. The current window resulted in an UP move despite these conditions. I will now investigate if the positive odds score has more predictive power than the 'Nitro' and 'VolSnap' combination.", "signal": "N/A", "winner": "UP", "outcome": "HOLD", "scanners_fired": ["Nitro", "VolSnap"], "1H_Trend": "S-DOWN", "Odds_Score": 93},
  {"Window": "btc-updown-5m-1774033200", "winner": "UP", "scanners_fired": ["Nitro", "VolSnap"], "1H_Trend": "S-DOWN", "Odds_Score": 93}
])

analyze_data(transformed_memory_data)
