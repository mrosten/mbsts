import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    nitro_hdo_up_trend_up_wins = 0
    nitro_hdo_up_trend_up_losses = 0
    nitro_hdo_down_trend_down_wins = 0
    nitro_hdo_down_trend_down_losses = 0
    nitro_hdo_total = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        winner = item.get('winner', 'N/A')

        if 'Nitro' in fired and 'HDO' in fired and len(fired) == 2:
            nitro_hdo_total += 1
            if trend == 'UP' and btc_move_pct > 0:
                if winner == 'UP':
                    nitro_hdo_up_trend_up_wins += 1
                else:
                    nitro_hdo_up_trend_up_losses += 1
            elif trend == 'DOWN' and btc_move_pct < 0:
                if winner == 'DOWN':
                    nitro_hdo_down_trend_down_wins += 1
                else:
                    nitro_hdo_down_trend_down_losses += 1

    print(f'Nitro + HDO, UP Trend & BTC Up - Wins: {nitro_hdo_up_trend_up_wins}, Losses: {nitro_hdo_up_trend_up_losses}')
    print(f'Nitro + HDO, DOWN Trend & BTC Down - Wins: {nitro_hdo_down_trend_down_wins}, Losses: {nitro_hdo_down_trend_down_losses}')
    print(f'Total Nitro+HDO Triggers: {nitro_hdo_total}')

except Exception as e:
    print(f'Runtime Error: {e}')