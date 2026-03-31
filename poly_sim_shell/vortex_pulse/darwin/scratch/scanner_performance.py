import json

# Load historical data (replace with your actual data loading mechanism)
historical_data = []

# Placeholder for fetching historical data. In reality, this would read from a database or file.
# for i in range(10):
#  historical_data.append({'Window ID': f'btc-updown-5m-{i}', 'Winner': 'UP', 'Scanners that fired': ['ScannerA', 'ScannerB']})

# Analyze scanner performance
scanner_counts = {}
for entry in historical_data:
    winner = entry['Winner']
    scanners = entry['Scanners that fired']
    for scanner in scanners:
        if scanner not in scanner_counts:
            scanner_counts[scanner] = {'UP': 0, 'DOWN': 0}
        scanner_counts[scanner][winner] += 1

# Print the analysis result
print(json.dumps(scanner_counts, indent=4))