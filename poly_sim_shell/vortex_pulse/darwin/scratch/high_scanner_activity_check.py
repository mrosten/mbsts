def analyze_data(data):
    high_activity_threshold = 7  # Number of scanners firing to be considered high activity
    
    recent_results = data[-10:]
    
    continuation_count = 0
    total_high_activity = 0
    
    for i in range(len(recent_results) - 1):
        current_window = recent_results[i]
        next_window = recent_results[i+1]
        
        if 'scanners_fired' in current_window and len(current_window['scanners_fired']) >= high_activity_threshold:
            total_high_activity += 1
            current_winner = current_window['winner']
            next_winner = next_window['winner']
            
            if current_winner == next_winner and current_winner != 'N/A' and next_winner != 'N/A':
                continuation_count += 1
    
    if total_high_activity > 0:
        continuation_rate = continuation_count / total_high_activity
        return continuation_rate
    else:
        return None


data = [
    {'window_id': 'btc-updown-5m-1774035000', 'winner': 'N/A', 'scanners_fired': ['Nitro', 'VolSnap']},
    {'window_id': 'btc-updown-5m-1774035000', 'winner': 'DOWN', 'scanners_fired': ['ADT', 'WCP', 'SSC']},
    {'window_id': 'btc-updown-5m-1774035300', 'winner': 'N/A', 'scanners_fired': ['Nitro', 'VolSnap']},
    {'window_id': 'btc-updown-5m-1774035600', 'winner': 'UP', 'scanners_fired': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {'window_id': 'btc-updown-5m-1774035900', 'winner': 'DOWN', 'scanners_fired': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {'window_id': 'btc-updown-5m-1774036200', 'winner': 'N/A', 'scanners_fired': ['Nitro', 'VolSnap']},
    {'window_id': 'btc-updown-5m-1774037400', 'winner': 'UP', 'scanners_fired': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {'window_id': 'btc-updown-5m-1774037700', 'winner': 'N/A', 'scanners_fired': ['Manual', 'Nitro', 'VolSnap']},
    {'window_id': 'btc-updown-5m-1774038000', 'winner': 'DOWN', 'scanners_fired': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT']},
    {'window_id': 'btc-updown-5m-1774038300', 'winner': 'DOWN', 'scanners_fired': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT', 'Darwin']}
]

continuation_rate = analyze_data(data)

if continuation_rate is not None:
    print(f"Continuation rate after high scanner activity: {continuation_rate:.2f}")
else:
    print("Not enough data with high scanner activity to calculate continuation rate.")
