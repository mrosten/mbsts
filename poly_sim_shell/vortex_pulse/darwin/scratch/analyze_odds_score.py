def analyze_data(memory):
    high_positive_odds_score_count = 0
    high_positive_odds_score_down_count = 0
    for window in memory:
        if 'Odds Score' in window and window['Odds Score'] > 80 and 'VolSnap' in window['Scanners that fired'] and 'Nitro' in window['Scanners that fired'] and window['1H Trend'] == 'S-DOWN':
            high_positive_odds_score_count += 1
            if window['winner'] == 'DOWN':
                high_positive_odds_score_down_count += 1
    if high_positive_odds_score_count > 0:
        down_ratio = high_positive_odds_score_down_count / high_positive_odds_score_count
        print(f"Windows with 'VolSnap', 'Nitro', S-DOWN 1H Trend, and Odds Score > 80: {high_positive_odds_score_count}")
        print(f"Down ratio: {down_ratio}")
    else:
        print("No windows found with 'VolSnap', 'Nitro', S-DOWN 1H Trend, and Odds Score > 80")


memory = [
  {'Window': 'btc-updown-5m-1774017300', 'hypothesis': 'Following an UP window with high scanner activity and a positive Odds Score, if the 1H Trend is S-DOWN, the next window is more likely to be DOWN despite the upward momentum.', 'signal': 'N/A', 'winner': 'UP', 'outcome': 'HOLD', 'Scanners that fired': [], 'Odds Score': 50, '1H Trend': 'S-DOWN'},
  {'Window': '1774017600', 'hypothesis': 'Following a significant DOWN move coupled with a negative \'Odds Score\' and the firing of \'WCP\', the market is likely to continue downwards.', 'signal': 'N/A', 'winner': 'N/A', 'outcome': 'HOLD', 'Scanners that fired': [], 'Odds Score': -20, '1H Trend': 'S-DOWN'},
  {'Window': 'btc-updown-5m-1774017600', 'hypothesis': 'After a UP window with a positive Odds Score, high scanner activity including \'Darwin\', and a S-DOWN 1H Trend, the next window is likely to be DOWN, but this time it was UP. Perhaps \'Darwin\' scanner firing is negatively correlated with DOWN moves when 1H Trend is S-DOWN.', 'signal': 'N/A', 'winner': 'UP', 'outcome': 'HOLD', 'Scanners that fired': ['Darwin'], 'Odds Score': 30, '1H Trend': 'S-DOWN'},
  {'Window': '1774017900', 'hypothesis': 'When \'Nitro\' and \'VolSnap\' fire together with S-DOWN 1H Trend and negative Odds Score, the market has a strong tendency to move DOWN.', 'signal': 'N/A', 'winner': 'N/A', 'outcome': 'HOLD', 'Scanners that fired': ['Nitro', 'VolSnap'], 'Odds Score': -10, '1H Trend': 'S-DOWN'},
  {'Window': '1774018200', 'hypothesis': 'When \'Nitro\' and \'VolSnap\' fire together with S-DOWN 1H Trend and negative Odds Score, the market has a strong tendency to move DOWN. I will test this further.', 'signal': 'N/A', 'winner': 'N/A', 'outcome': 'HOLD', 'Scanners that fired': ['Nitro', 'VolSnap'], 'Odds Score': -5, '1H Trend': 'S-DOWN'},
  {'Window': 'btc-updown-5m-1774018200', 'hypothesis': 'When \'Nitro\' and \'VolSnap\' fire together with S-DOWN 1H Trend and positive Odds Score, the market has a tendency to move DOWN. The negative Odds Score was incorrectly applied in the last window, it was actually positive. I will test this.', 'signal': 'N/A', 'winner': 'DOWN', 'outcome': 'HOLD', 'Scanners that fired': ['Nitro', 'VolSnap'], 'Odds Score': 20, '1H Trend': 'S-DOWN'},
  {'Window': '1774018500', 'hypothesis': 'When \'Nitro\' and \'VolSnap\' fire together with S-DOWN 1H Trend, regardless of Odds Score (positive OR negative), the market has a tendency to move DOWN. I will test this further.', 'signal': 'N/A', 'winner': 'N/A', 'outcome': 'HOLD', 'Scanners that fired': ['Nitro', 'VolSnap'], 'Odds Score': 10, '1H Trend': 'S-DOWN'},
  {'Window': 'btc-updown-5m-1774018500', 'hypothesis': 'The firing of \'Nitro\' and \'VolSnap\' together with a S-DOWN 1H trend is not consistently predicting DOWN moves. The current window resulted in an UP move despite these conditions. I will now investigate if the positive odds score has more predictive power than the \'Nitro\' and \'VolSnap\' combination.', 'signal': 'N/A', 'winner': 'UP', 'outcome': 'HOLD', 'Scanners that fired': ['Nitro', 'VolSnap'], 'Odds Score': 40, '1H Trend': 'S-DOWN'},
  {'Window': 'btc-updown-5m-1774018800', 'hypothesis': 'High scanner activity combined with a negative \'Odds Score\' following a DOWN window indicates a continuation of the downward trend.', 'signal': 'N/A', 'winner': 'DOWN', 'outcome': 'HOLD', 'Scanners that fired': [], 'Odds Score': -30, '1H Trend': 'S-DOWN'},
  {'Window': 'btc-updown-5m-1774019100', 'hypothesis': 'Following a DOWN window with high scanner activity and a positive \'Odds Score\', the next window is likely to be DOWN, potentially indicating a delayed reaction to initial downward pressure.', 'signal': 'N/A', 'winner': 'DOWN', 'outcome': 'HOLD', 'Scanners that fired': [], 'Odds Score': 60, '1H Trend': 'S-DOWN'}
]

analyze_data(memory)