def analyze_data(memory):
    fakeout_count = 0
    total_count = 0
    for window in memory:
        if 'scanners_fired' in window and len(window['scanners_fired']) > 5 and window['btc_move'] < 0:
            total_count += 1
            future_window = memory[memory.index(window) + 1] if memory.index(window) + 1 < len(memory) else None
            if future_window and future_window['btc_move'] < 0:
                fakeout_count += 1
    if total_count > 0:
        fakeout_percentage = (fakeout_count / total_count) * 100
        print(f"Percentage of High Activity DOWN followed by another DOWN: {fakeout_percentage:.2f}% (based on {total_count} instances)")
    else:
        print("Not enough data to analyze.")


memory = [
    {
        'scanners_fired': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing', 'WCP', 'SSC', 'ADT', 'Darwin'],
        'btc_move': -0.000,
    },
        {
        'scanners_fired': ['Nitro', 'VolSnap'],
        'btc_move': 0.001,
    },
            {
        'scanners_fired': ['MM2', 'GrindSnap', 'Nitro', 'VolSnap', 'Briefing'],
        'btc_move': -0.0001,
    },
    {
        'btc_move': -0.0005
    }
]

analyze_data(memory)