import json

trend_wins = 0
trend_losses = 0
total_triggers = 0

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)
    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)

        if 'Nitro' in fired and len(fired) == 1:
            total_triggers += 1
            if (trend == 'UP' and btc_move_pct > 0) or (trend == 'DOWN' and btc_move_pct < 0):
                trend_wins += 1
            else:
                trend_losses += 1

    print(f'Nitro Only, UP Trend & BTC Up - Wins: {trend_wins}, Losses: {trend_losses}')
    print(f'Nitro Only, DOWN Trend & BTC Down - Wins: {trend_wins}, Losses: {trend_losses}')
    print(f'Total Nitro Only Triggers: {total_triggers}')

except Exception as e:
    print(f'Runtime Error: {e}')