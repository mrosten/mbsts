def analyze_briefing_odds(data):
    """Analyzes historical data for windows where 'Briefing' fired with high positive Odds Scores."""
    relevant_windows = []
    for window_id, window_data in data.items():
        if 'scanners' in window_data and 'Briefing' in window_data['scanners'] and 'odds_score' in window_data and window_data['odds_score'] > 90:
            relevant_windows.append(window_data)

    if not relevant_windows:
        print("No relevant windows found.")
        return

    up_count = 0
    down_count = 0
    for window in relevant_windows:
        if 'winner' in window and window['winner'] == 'UP':
            up_count += 1
        elif 'winner' in window and window['winner'] == 'DOWN':
            down_count += 1

    total_windows = len(relevant_windows)
    if total_windows > 0:
        up_percentage = (up_count / total_windows) * 100
        down_percentage = (down_count / total_windows) * 100
        print(f"Total windows with 'Briefing' and Odds Score > 90: {total_windows}")
        print(f"UP Percentage: {up_percentage:.2f}% ({up_count} windows)")
        print(f"DOWN Percentage: {down_percentage:.2f}% ({down_count} windows)")
    else:
        print("No relevant windows found for analysis.")


data = {
    '1774019100': {'scanners': ['Briefing'], 'odds_score': 95, 'winner': 'UP'},
    '1774019400': {'scanners': ['Briefing', 'ADT'], 'odds_score': 92, 'winner': 'UP'},
    '1774019700': {'scanners': ['Briefing', 'WCP'], 'odds_score': 85, 'winner': 'DOWN'},
    '1774020000': {'scanners': ['Briefing', 'NIT'], 'odds_score': 98, 'winner': 'UP'},
    '1774032300': {'scanners': ['Briefing'], 'odds_score': 91, 'winner': 'UP'},
    '1774032600': {'scanners': ['VolSnap', 'Nitro'], 'odds_score': 70, 'winner': 'UP'},
    '1774032900': {'scanners': ['ADT', 'WCP', 'SSC'], 'odds_score': 20, 'winner': 'DOWN'},
    '1774033200': {'scanners': ['Nitro', 'VolSnap'], 'odds_score': 99, 'winner': 'UP'},
    '1774033500': {'scanners': ['ADT', 'WCP', 'SSC'], 'odds_score': -10, 'winner': 'DOWN'},
    '1774033800': {'scanners': ['WCP', 'Nitro', 'VolSnap'], 'odds_score': 10, 'winner': 'UP'},
    '1774033800': {'scanners': ['ADT', 'WCP', 'SSC'], 'odds_score': -20, 'winner': 'UP'},
    '1774034100': {'scanners': ['Briefing'], 'odds_score': 97}
}

analyze_briefing_odds(data)