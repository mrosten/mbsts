import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    up_wins = 0
    up_losses = 0
    down_wins = 0
    down_losses = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        odds_score = mdata.get('odds_score', 0.0)
        winner = item.get('winner', 'N/A')
        
        if len(fired) == 1 and 'GrindSnap' in fired:
            if trend == 'S-UP' and odds_score > 0:
                if winner == 'UP':
                    up_wins += 1
                elif winner == 'DOWN':
                    up_losses += 1
            elif trend == 'S-DOWN' and odds_score < 0:
                if winner == 'DOWN':
                    down_wins += 1
                elif winner == 'UP':
                    down_losses += 1

    print(f"GrindSnap fired alone:\n")
    print(f"S-UP Trend, Odds > 0, UP predictions: Wins={up_wins}, Losses={up_losses}\n")
    print(f"S-DOWN Trend, Odds < 0, DOWN predictions: Wins={down_wins}, Losses={down_losses}")

except Exception as e:
    print(f'Runtime Error: {e}')
