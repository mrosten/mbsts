import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    ssc_up_wins = 0
    ssc_up_losses = 0
    ssc_down_wins = 0
    ssc_down_losses = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired_scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        winner = item.get('winner', 'N/A')
        odds_score = mdata.get('odds_score', 0.0)

        if len(fired_scanners) == 1 and 'SSC' in fired_scanners:
            if trend == 'S-UP':
                if winner == 'UP':
                    ssc_up_wins += 1
                elif winner == 'DOWN':
                    ssc_up_losses += 1
            elif trend == 'S-DOWN':
                if winner == 'DOWN':
                    ssc_down_wins += 1
                elif winner == 'UP':
                    ssc_down_losses += 1

    print(f"SSC fired alone:\n")
    print(f"S-UP Trend, UP predictions: Wins={ssc_up_wins}, Losses={ssc_up_losses}\n")
    print(f"S-DOWN Trend, DOWN predictions: Wins={ssc_down_wins}, Losses={ssc_down_losses}\n")

except Exception as e:
    print(f'Runtime Error: {e}')