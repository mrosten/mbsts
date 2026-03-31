import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    nitro_alone_up_wins = 0
    nitro_alone_up_losses = 0
    nitro_alone_down_wins = 0
    nitro_alone_down_losses = 0
    hdo_alone_up_wins = 0
    hdo_alone_up_losses = 0
    hdo_alone_down_wins = 0
    hdo_alone_down_losses = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'NEUTRAL')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        winner = item.get('winner', 'N/A')

        if 'NIT' in fired and len(fired) == 1:
            if trend in ['DOWN', 'M-DOWN', 'S-DOWN']:
                if winner == 'UP':
                    nitro_alone_up_wins += 1
                elif winner == 'DOWN':
                    nitro_alone_up_losses += 1
            elif trend in ['UP', 'M-UP', 'S-UP']:
                if winner == 'DOWN':
                    nitro_alone_down_wins += 1
                elif winner == 'UP':
                    nitro_alone_down_losses += 1
        
        if 'HDO' in fired and len(fired) == 1:
            if trend in ['DOWN', 'M-DOWN', 'S-DOWN']:
                if winner == 'UP':
                    hdo_alone_up_wins += 1
                elif winner == 'DOWN':
                    hdo_alone_up_losses += 1
            elif trend in ['UP', 'M-UP', 'S-UP']:
                if winner == 'DOWN':
                    hdo_alone_down_wins += 1
                elif winner == 'UP':
                    hdo_alone_down_losses += 1

    print(f'Nitro alone UP predictions: Wins={nitro_alone_up_wins}, Losses={nitro_alone_up_losses}')
    print(f'Nitro alone DOWN predictions: Wins={nitro_alone_down_wins}, Losses={nitro_alone_down_losses}')
    print(f'HDO alone UP predictions: Wins={hdo_alone_up_wins}, Losses={hdo_alone_up_losses}')
    print(f'HDO alone DOWN predictions: Wins={hdo_alone_down_wins}, Losses={hdo_alone_down_losses}')

except Exception as e:
    print(f'Runtime Error: {e}')