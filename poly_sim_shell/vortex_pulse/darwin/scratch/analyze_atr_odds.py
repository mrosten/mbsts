import statistics

memory = [
    {"window_id": "btc-updown-5m-1774034100", "winner": "UP", "atr": 0.1, "odds_score": -10.0, "scanners": ['VolSnap', 'Nitro', 'GrindSnap']},
    {"window_id": "1774034400", "winner": "UP", "atr": 0.05, "odds_score": -5.0, "scanners": ['VolSnap']},
    {"window_id": "btc-updown-5m-1774034400", "winner": "UP", "atr": 0.2, "odds_score": -20.0, "scanners": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {"window_id": "1774034700", "winner": "DOWN", "atr": 0.15, "odds_score": 5.0, "scanners": ['VolSnap']},
    {"window_id": "1774035000", "winner": "DOWN", "atr": 0.1, "odds_score": 2.0, "scanners": ['Nitro', 'VolSnap']},
    {"window_id": "btc-updown-5m-1774035000", "winner": "DOWN", "atr": 0.08, "odds_score": -3.0, "scanners": ['ADT', 'WCP', 'SSC']},
    {"window_id": "1774035300", "winner": "DOWN", "atr": 0.12, "odds_score": -1.0, "scanners": ['Nitro', 'VolSnap']},
    {"window_id": "btc-updown-5m-1774035600", "winner": "UP", "atr": 0.25, "odds_score": 15.0, "scanners": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {"window_id": "btc-updown-5m-1774035900", "winner": "DOWN", "atr": 0.18, "odds_score": -12.0, "scanners": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {"window_id": "1774036200", "winner": "UP", "atr": 0.3, "odds_score": 8.0, "scanners": ['Nitro', 'VolSnap']}
]

up_count = 0
down_count = 0

for item in memory:
  if item["atr"] < 0.1 and item["odds_score"] < 0 and len(item["scanners"]) > 5:
    if item["winner"] == "UP":
      up_count += 1
    else:
      down_count += 1

total_count = up_count + down_count

if total_count > 0:
  up_percentage = (up_count / total_count) * 100
  down_percentage = (down_count / total_count) * 100
  print(f"UP Percentage: {up_percentage:.2f}%\nDOWN Percentage: {down_percentage:.2f}%\nTotal Occurrences: {total_count}")
else:
  print("No matching historical data found.")