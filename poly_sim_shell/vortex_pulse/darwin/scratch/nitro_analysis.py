import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    up_trend_up_wins = 0
    up_trend_up_losses = 0
    down_trend_down_wins = 0
    down_trend_down_losses = 0
    total_nitro_triggers = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired_scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        winner = item.get('winner', 'N/A')

        if 'Nitro' in fired_scanners and len(fired_scanners) == 1:
            total_nitro_triggers += 1
            if trend == 'UP' and btc_move_pct > 0:
                if winner == 'UP':
                    up_trend_up_wins += 1
                else:
                    up_trend_up_losses += 1
            elif trend == 'DOWN' and btc_move_pct < 0:
                if winner == 'DOWN':
                    down_trend_down_wins += 1
                else:
                    down_trend_down_losses += 1

    print(f'Nitro Only, UP Trend & BTC Up - Wins: {up_trend_up_wins}, Losses: {up_trend_up_losses}')
    print(f'Nitro Only, DOWN Trend & BTC Down - Wins: {down_trend_down_wins}, Losses: {down_trend_down_losses}')
    print(f'Total Nitro Only Triggers: {total_nitro_triggers}')

except Exception as e:
    print(f'Runtime Error: {e}')