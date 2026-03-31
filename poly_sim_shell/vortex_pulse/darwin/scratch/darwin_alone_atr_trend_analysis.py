import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    up_up_wins = 0
    up_up_losses = 0
    up_down_wins = 0
    up_down_losses = 0
    down_up_wins = 0
    down_up_losses = 0
    down_down_wins = 0
    down_down_losses = 0

    for i in range(1, len(history)):
        current = history[i]
        previous = history[i-1]

        current_fired = current.get('market_data', {}).get('fired_scanners', [])
        current_trend = current.get('market_data', {}).get('trend_1h', 'N/A')
        previous_btc_move = previous.get('market_data', {}).get('btc_move_pct', 0.0)
        current_winner = current.get('winner', 'N/A')

        if 'Darwin' in current_fired and len(current_fired) == 1:
            if previous_btc_move < 0:
                if current_trend == 'S-UP':
                    if current_winner == 'UP':
                        up_up_wins += 1
                    elif current_winner == 'DOWN':
                        up_up_losses += 1
                elif current_trend == 'S-DOWN':
                    if current_winner == 'DOWN':
                        down_down_wins += 1
                    elif current_winner == 'UP':
                        down_down_losses += 1
            elif previous_btc_move > 0:
                if current_trend == 'S-UP':
                    if current_winner == 'UP':
                        down_up_wins += 1
                    elif current_winner == 'DOWN':
                        down_up_losses += 1
                elif current_trend == 'S-DOWN':
                    if current_winner == 'DOWN':
                        up_down_wins += 1
                    elif current_winner == 'UP':
                        up_down_losses += 1

    print(f"Previous BTC Down, S-UP Trend: Wins={up_up_wins}, Losses={up_up_losses}")
    print(f"Previous BTC Down, S-DOWN Trend: Wins={down_down_wins}, Losses={down_down_losses}")
    print(f"Previous BTC Up, S-UP Trend: Wins={down_up_wins}, Losses={down_up_losses}")
    print(f"Previous BTC Up, S-DOWN Trend: Wins={up_down_wins}, Losses={up_down_losses}")

except Exception as e:
    print(f'Runtime Error: {e}')