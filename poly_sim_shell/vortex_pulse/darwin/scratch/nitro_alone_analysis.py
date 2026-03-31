import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    nitro_alone_up_wins = 0
    nitro_alone_up_losses = 0
    nitro_alone_down_wins = 0
    nitro_alone_down_losses = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired_scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'NEUTRAL')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        odds_score = mdata.get('odds_score', 0.0)
        atr_5m = mdata.get('atr_5m', 0.0)
        winner = item.get('winner', 'N/A')

        if 'NIT' in fired_scanners and 'HDO' not in fired_scanners and 'BRI' not in fired_scanners and len(fired_scanners) == 1:
            if trend in ['DOWN', 'M-DOWN', 'S-DOWN']:
                #Stricter condition: odds_score > 2 * atr_5m
                if odds_score > 2 * atr_5m:
                    if winner == 'UP':
                        nitro_alone_up_wins += 1
                    elif winner == 'DOWN':
                        nitro_alone_up_losses += 1
            elif trend in ['UP', 'M-UP', 'S-UP']:
                #Stricter Condition: abs(odds_score) > 2 * atr_5m
                if abs(odds_score) > 2 * atr_5m:
                    if winner == 'DOWN':
                        nitro_alone_down_wins += 1
                    elif winner == 'UP':
                        nitro_alone_down_losses += 1

    print('Nitro alone UP predictions: Wins={}, Losses={}'.format(nitro_alone_up_wins, nitro_alone_up_losses))
    print('Nitro alone DOWN predictions: Wins={}, Losses={}'.format(nitro_alone_down_wins, nitro_alone_down_losses))

except Exception as e:
    print(f'Runtime Error: {e}')
