import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    vsn_alone_up_wins = 0
    vsn_alone_up_losses = 0
    vsn_alone_down_wins = 0
    vsn_alone_down_losses = 0
    
    btc_move_threshold = 0.05  # Adjust this threshold as needed

    for item in history:
        mdata = item.get('market_data', {})
        fired_scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'NEUTRAL')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        winner = item.get('winner', 'N/A')

        if 'VSN' in fired_scanners and len(fired_scanners) == 1:
            if trend in ['DOWN', 'M-DOWN', 'S-DOWN'] and btc_move_pct > -btc_move_threshold:
                if winner == 'DOWN':
                    vsn_alone_down_wins += 1
                else:
                    vsn_alone_down_losses += 1
            elif trend in ['UP', 'M-UP', 'S-UP'] and btc_move_pct < btc_move_threshold:
                if winner == 'UP':
                    vsn_alone_up_wins += 1
                else:
                    vsn_alone_up_losses += 1

    print(f'VSN alone UP predictions: Wins={vsn_alone_up_wins}, Losses={vsn_alone_up_losses}')
    print(f'VSN alone DOWN predictions: Wins={vsn_alone_down_wins}, Losses={vsn_alone_down_losses}')

except Exception as e:
    print(f'Runtime Error: {e}')