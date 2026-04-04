import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    up_trend_up_wins = 0
    up_trend_up_losses = 0
    down_trend_down_wins = 0
    down_trend_down_losses = 0

    total_triggers = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)

        if 'Nitro' in fired and 'VolSnap' in fired and len(fired) == 2:
            total_triggers += 1
            if trend == 'UP':
                if btc_move_pct > 0:
                    up_trend_up_wins += 1
                else:
                    up_trend_up_losses += 1
            elif trend == 'DOWN':
                if btc_move_pct < 0:
                    down_trend_down_wins += 1
                else:
                    down_trend_down_losses += 1

    print(f"Nitro + VolSnap, UP Trend & BTC Up - Wins: {up_trend_up_wins}, Losses: {up_trend_up_losses}\n"+
          f"Nitro + VolSnap, DOWN Trend & BTC Down - Wins: {down_trend_down_wins}, Losses: {down_trend_down_losses}\n"+
          f"Total Nitro+VolSnap Triggers: {total_triggers}")

except Exception as e:
    print(f'Runtime Error: {e}')