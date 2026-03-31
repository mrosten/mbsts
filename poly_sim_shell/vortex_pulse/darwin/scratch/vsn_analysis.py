import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    s_down_wins = 0
    s_down_losses = 0

    for item in history:
        mdata = item.get('market_data', {})
        trend = mdata.get('trend_1h', 'N/A')
        scanners = mdata.get('fired_scanners', [])
        btc_move = mdata.get('btc_move_pct', 0.0)
        odds = mdata.get('odds_score', 0.0)
        atr = mdata.get('atr_5m', 0.0)
        winner = item.get('winner', 'N/A')

        if 'VSN' in scanners and len(scanners) == 1 and trend == 'S-DOWN':
            if winner == 'UP':
                s_down_losses += 1
            elif winner == 'DOWN':
                s_down_wins += 1

    print(f'S-DOWN VSN alone: Wins={s_down_wins}, Losses={s_down_losses}')

except Exception as e:
    print(f'Error processing history: {e}')