import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    volsnap_alone_up_wins = 0
    volsnap_alone_up_losses = 0
    volsnap_alone_down_wins = 0
    volsnap_alone_down_losses = 0
    total_volsnap_alone = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        odds_score = mdata.get('odds_score', 0.0)
        atr_5m = mdata.get('atr_5m', 0.0)
        if 'VolSnap' in fired and len(fired) == 1:
            total_volsnap_alone +=1
            if trend in ['UP', 'M-UP', 'S-UP']:
                outcome = item.get('outcome', 'HOLD')
                if outcome == 'WIN_UP':
                    volsnap_alone_up_wins += 1
                elif outcome == 'LOSE_UP':
                    volsnap_alone_up_losses += 1
            elif trend in ['DOWN', 'M-DOWN', 'S-DOWN']:
                outcome = item.get('outcome', 'HOLD')
                if outcome == 'WIN_DOWN':
                    volsnap_alone_down_wins += 1
                elif outcome == 'LOSE_DOWN':
                    volsnap_alone_down_losses += 1

    print(f'VolSnap alone, trend aligned:\n\nUP predictions: Wins={volsnap_alone_up_wins}, Losses={volsnap_alone_up_losses}\n\nDOWN predictions: Wins={volsnap_alone_down_wins}, Losses={volsnap_alone_down_losses}')
    print(f'Total VolSnap Alone = {total_volsnap_alone}')

except Exception as e:
    print(f'Runtime Error: {e}')
