import json

def analyze_adt(data):
    adt_up_successes = 0
    adt_up_failures = 0
    total_adt_up = 0

    for window in data:
        if 'scanners' in window and 'Odds Score' in window and 'BTC Move' in window:
            if 'ADT' in window['scanners'] and window['BTC Move'] > 0 and window['Odds Score'] > 0:
                total_adt_up += 1
                if window['winner'] == 'UP':
                    adt_up_successes += 1
                else:
                    adt_up_failures += 1

    print(f"Total ADT firings after positive BTC move and Odds Score: {total_adt_up}")
    if total_adt_up > 0:
        success_rate = adt_up_successes / total_adt_up
        print(f"Success rate (UP following ADT): {success_rate:.2f}")
    else:
        print("No data available for ADT firings after positive BTC move and Odds Score.")

# Load historical data (replace 'your_data.json' with the actual file)
# Since we can't access external files, we will mock the data
mock_data = [
    {
        'window_id': '1',
        'scanners': ['ADT', 'Nitro'],
        'Odds Score': 50,
        'BTC Move': 0.001,
        'winner': 'UP'
    },
    {
        'window_id': '2',
        'scanners': ['ADT'],
        'Odds Score': 20,
        'BTC Move': 0.0005,
        'winner': 'UP'
    },
    {
        'window_id': '3',
        'scanners': ['ADT', 'VolSnap'],
        'Odds Score': 30,
        'BTC Move': 0.0001,
        'winner': 'DOWN'
    },
    {
        'window_id': '4',
        'scanners': ['Nitro'],
        'Odds Score': 10,
        'BTC Move': 0.0002,
        'winner': 'UP'
    },
    {
        'window_id': '5',
        'scanners': ['ADT'],
        'Odds Score': 40,
        'BTC Move': 0.0009,
        'winner': 'UP'
    }
]

analyze_adt(mock_data)
