import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    bri_volsnap_up_wins = 0
    bri_volsnap_up_losses = 0
    bri_volsnap_down_wins = 0
    bri_volsnap_down_losses = 0

    for item in history:
        mdata = item.get('market_data', {})
        scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)

        if 'BRI' in scanners and 'VolSnap' in scanners:
            if trend == 'M-UP' or trend == 'UP' or trend == 'S-UP':
                if btc_move_pct > 0:
                    bri_volsnap_up_wins += 1
                else:
                    bri_volsnap_up_losses += 1
            elif trend == 'M-DOWN' or trend == 'DOWN' or trend == 'S-DOWN':
                if btc_move_pct < 0:
                    bri_volsnap_down_wins += 1
                else:
                    bri_volsnap_down_losses += 1

    print(f'BRI and VolSnap Firing Together:\n')
    print(f'UP predictions: Wins={bri_volsnap_up_wins}, Losses={bri_volsnap_up_losses}')
    print(f'DOWN predictions: Wins={bri_volsnap_down_wins}, Losses={bri_volsnap_down_losses}')

except Exception as e:
    print(f'Runtime Error: {e}')