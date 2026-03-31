def analyze_data(data):
    down_count = 0
    total_count = 0
    for window in data:
        if len(window['Scanners that fired']) > 5 and window['Winner'] == 'DOWN' and window['Odds Score'] < 0:
            total_count += 1
            down_count += 1
        elif len(window['Scanners that fired']) > 5 and window['Odds Score'] < 0:
            total_count += 1

    if total_count > 0:
        down_percentage = (down_count / total_count)
        return down_percentage
    else:
        return 0.0

# Example usage (replace with actual data loading)
data = [
    {"Scanners that fired": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT', 'Darwin'], "Winner": 'DOWN', "Odds Score": -21.0},
    {"Scanners that fired": ['MM2', 'GrindSnap'], "Winner": 'UP', "Odds Score": -5.0},
    {"Scanners that fired": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT', 'Darwin'], "Winner": 'DOWN', "Odds Score": -15.0},
    {"Scanners that fired": ['MM2'], "Winner": 'UP', "Odds Score": 10.0},
    {"Scanners that fired": ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT', 'Darwin'], "Winner": 'DOWN', "Odds Score": -30.0}
]

down_probability = analyze_data(data)
print(f"Probability of DOWN move after high scanner activity and negative odds: {down_probability}")