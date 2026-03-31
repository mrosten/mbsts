import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    nitro_up_wins = 0
    nitro_up_losses = 0
    nitro_down_wins = 0
    nitro_down_losses = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move = mdata.get('btc_move_pct', 0.0)
        winner = item.get('winner', 'N/A')

        if len(fired) == 1 and 'Nitro' in fired:
            if trend == 'S-UP':
                if btc_move > 0:
                    if winner == 'UP':
                        nitro_up_wins += 1
                    elif winner == 'DOWN':
                        nitro_up_losses += 1
            elif trend == 'S-DOWN':
                if btc_move < 0:
                    if winner == 'DOWN':
                        nitro_down_wins += 1
                    elif winner == 'UP':
                        nitro_down_losses += 1

    print(f"Nitro fired alone:\n")
    print(f"S-UP Trend, UP predictions: Wins={nitro_up_wins}, Losses={nitro_up_losses}\n")
    print(f"S-DOWN Trend, DOWN predictions: Wins={nitro_down_wins}, Losses={nitro_down_losses}")

except Exception as e:
    print(f'Runtime Error: {e}')
