import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    vol_snap_alone_up_wins = 0
    vol_snap_alone_up_losses = 0
    vol_snap_alone_down_wins = 0
    vol_snap_alone_down_losses = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        if len(fired) == 1 and 'VSN' in fired:
            if btc_move_pct > 0:
                if item.get('winner') == 'DOWN':
                    vol_snap_alone_up_losses += 1
                else:
                    vol_snap_alone_up_wins += 1
            else:
                if item.get('winner') == 'UP':
                    vol_snap_alone_down_losses += 1
                else:
                    vol_snap_alone_down_wins += 1

    print(f'VolSnap alone UP predictions: Wins={vol_snap_alone_up_wins}, Losses={vol_snap_alone_up_losses}')
    print(f'VolSnap alone DOWN predictions: Wins={vol_snap_alone_down_wins}, Losses={vol_snap_alone_down_losses}')

except Exception as e:
    print(f'Runtime Error: {e}')