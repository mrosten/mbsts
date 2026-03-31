# This script analyzes the historical performance of 'Darwin' when it fires alone after a DOWN move.

import json

def analyze_data(filename="darwin_memory.json"): # Dummy filename - assume the bot has access to the memory
    try:
        # Load memory from dummy file
        with open(filename, 'r') as f:
            memory = json.load(f)

        # Extract relevant data
        relevant_data = []
        for window in memory.get('windows', []):
            if 'scanners_fired' in window and 'winner' in window and 'btc_move' in window:
                if window['scanners_fired'] == ['Darwin'] and window['btc_move'] < 0:
                    relevant_data.append({'winner': window['winner'], 'btc_move': window['btc_move']})

        # Analyze performance
        if relevant_data:
            up_count = sum(1 for item in relevant_data if item['winner'] == 'UP')
            down_count = sum(1 for item in relevant_data if item['winner'] == 'DOWN')
            total_count = len(relevant_data)

            if total_count > 0:
                up_percentage = (up_count / total_count) * 100
                down_percentage = (down_count / total_count) * 100

                print(f"Total occurrences: {total_count}")
                print(f"UP predictions: {up_count} ({up_percentage:.2f}%)")
                print(f"DOWN predictions: {down_count} ({down_percentage:.2f}%)")

                # Determine the dominant outcome
                if up_percentage > down_percentage:
                    print("Bias: UP (Potential counter-trend signal)")
                elif down_percentage > up_percentage:
                    print("Bias: DOWN (Continuation signal)")
                else:
                    print("No clear bias")
            else:
                print("No relevant data found.")
        else:
            print("No relevant data found.")

    except FileNotFoundError:
        print(f"Error: The file '{filename}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


analyze_data()
