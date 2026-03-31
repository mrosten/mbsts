def analyze_data(data):
    target_scanners = ['WCP', 'Nitro', 'VolSnap']
    up_count = 0
    down_count = 0
    total_count = 0

    for window in data:
        if 'scanners_fired' in window and 'odds_score' in window and 'next_window_tilt' in window and window['next_window_tilt'] == 'None':
            scanners_fired = window['scanners_fired']
            odds_score = window['odds_score']
            winner = window.get('winner')

            if all(scanner in scanners_fired for scanner in target_scanners) and odds_score > 50:
                total_count += 1
                if winner == 'UP':
                    up_count += 1
                elif winner == 'DOWN':
                    down_count += 1

    if total_count > 0:
        up_ratio = up_count / total_count
        down_ratio = down_count / total_count
        print(f"Total windows matching criteria: {total_count}")
        print(f"UP ratio: {up_ratio:.2f}")
        print(f"DOWN ratio: {down_ratio:.2f}")
    else:
        print("No windows matching criteria found.")

data = [
    {'scanners_fired': ['WCP', 'Nitro', 'VolSnap'], 'odds_score': 98.0, 'next_window_tilt': 'None', 'winner': 'UP'},
    {'scanners_fired': ['WCP', 'Nitro', 'VolSnap', 'ADT'], 'odds_score': 60.0, 'next_window_tilt': 'None', 'winner': 'UP'},
    {'scanners_fired': ['WCP', 'Nitro', 'VolSnap'], 'odds_score': 70.0, 'next_window_tilt': 'None', 'winner': 'UP'},
    {'scanners_fired': ['WCP', 'Nitro', 'VolSnap'], 'odds_score': 30.0, 'next_window_tilt': 'None', 'winner': 'DOWN'},
    {'scanners_fired': ['WCP', 'Nitro'], 'odds_score': 80.0, 'next_window_tilt': 'DOWN', 'winner': 'UP'},
    {'scanners_fired': ['WCP'], 'odds_score': 90.0, 'next_window_tilt': 'UP', 'winner': 'DOWN'}
]

analyze_data(data)