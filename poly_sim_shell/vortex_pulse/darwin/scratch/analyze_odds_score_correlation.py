import statistics

# Placeholder for historical data retrieval - replace with actual data access
historical_data = [
    {"window_id": "btc-updown-5m-1774014300", "winner": "DOWN", "odds_score": 0.20, "scanners": 5},
    {"window_id": "btc-updown-5m-1774014600", "winner": "N/A", "odds_score": -0.10, "scanners": 2},
    {"window_id": "btc-updown-5m-1774015800", "winner": "DOWN", "odds_score": 0.27, "scanners": 9},
    {"window_id": "btc-updown-5m-1774012000", "winner": "UP", "odds_score": 0.35, "scanners": 7},
    {"window_id": "btc-updown-5m-1774011000", "winner": "DOWN", "odds_score": 0.15, "scanners": 6},
    {"window_id": "btc-updown-5m-1774010000", "winner": "UP", "odds_score": -0.20, "scanners": 3},
    {"window_id": "btc-updown-5m-1774009000", "winner": "DOWN", "odds_score": 0.25, "scanners": 8},
    {"window_id": "btc-updown-5m-1774008000", "winner": "DOWN", "odds_score": 0.30, "scanners": 10},
    {"window_id": "btc-updown-5m-1774007000", "winner": "UP", "odds_score": -0.05, "scanners": 4},
    {"window_id": "btc-updown-5m-1774006000", "winner": "DOWN", "odds_score": 0.10, "scanners": 7},
]


down_after_positive_odds = 0
down_total = 0

for i in range(1, len(historical_data)):
    if historical_data[i-1]['winner'] == 'DOWN' and historical_data[i-1]['odds_score'] > 0 and historical_data[i]['winner'] == 'DOWN':
        down_after_positive_odds += 1
    if historical_data[i]['winner'] == 'DOWN':
      down_total += 1

if down_total > 0:
  probability = down_after_positive_odds / down_total
else:
  probability = 0

print(f"Probability of DOWN after positive odds and previous DOWN: {probability}")

scanner_counts = [d['scanners'] for d in historical_data]
mean_scanner_count = statistics.mean(scanner_counts)
print(f"Mean Scanner Count: {mean_scanner_count}")
