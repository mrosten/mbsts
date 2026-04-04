import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    wins = 0
    losses = 0
    total_triggers = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        trend = mdata.get('trend_1h', 'NEUTRAL')

        if 'HDO' in fired and 'VolSnap' in fired:
            total_triggers += 1
            if (trend == 'UP' and btc_move_pct > 0) or (trend == 'DOWN' and btc_move_pct < 0):
                wins += 1
            else:
                losses += 1

    print(f'HDO+VolSnap, UP Trend & BTC Up (or DOWN Trend & BTC Down) - Wins: {wins}, Losses: {losses}')
    print(f'Total HDO+VolSnap Triggers: {total_triggers}')

except Exception as e:
    print(f'Runtime Error: {e}')