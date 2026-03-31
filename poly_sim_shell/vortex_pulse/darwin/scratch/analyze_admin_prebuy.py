# This script analyzes the historical performance of the 'Admin_PreBuy' scanner when it fires alone.

import json

memory_file = 'memory.json'

# Load memory from file
def load_memory(filename):
    try:
        with open(filename, 'r') as f:
            memory = json.load(f)
        return memory
    except FileNotFoundError:
        return []

# Get window result
def get_window_result(memory, window_id):
    for item in memory:
        if 'Window' in item and str(window_id) in item['Window']:
            return item
    return None


# Analyze 'Admin_PreBuy' performance
def analyze_admin_prebuy(memory):
    up_count = 0
    down_count = 0
    total_count = 0

    for item in memory:
        if 'Window ID' in item:
            window_id = item['Window ID']
            window_result = get_window_result(memory, window_id)
            if window_result and 'Scanners that fired' in window_result and window_result['Scanners that fired'] == ['Admin_PreBuy']:
                total_count += 1
                btc_move = window_result.get('BTC Move', 0)
                if btc_move > 0:
                    up_count += 1
                else:
                    down_count += 1
    return up_count, down_count, total_count

memory = load_memory(memory_file)

up_count, down_count, total_count = analyze_admin_prebuy(memory)

print(f"'Admin_PreBuy' fired alone {total_count} times.")
print(f"UP predictions: {up_count}")
print(f"DOWN predictions: {down_count}")

if total_count > 0:
    accuracy = up_count / total_count
    print(f"Accuracy: {accuracy:.2f}")
else:
    print("No data available for 'Admin_PreBuy' scanner firing alone.")