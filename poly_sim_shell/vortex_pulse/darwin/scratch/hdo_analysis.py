import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    hdo_up_trend_up_wins = 0
    hdo_up_trend_up_losses = 0
    hdo_down_trend_down_wins = 0
    hdo_down_trend_down_losses = 0
    total_hdo_triggers = 0

    for item in history:
        mdata = item.get('market_data', {})
        scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        winner = item.get('winner', 'N/A')

        if 'HDO' in scanners and len(scanners) == 1:
            total_hdo_triggers += 1
            if trend == 'UP' and btc_move_pct > 0:
                if winner == 'UP':
                    hdo_up_trend_up_wins += 1
                else:
                    hdo_up_trend_up_losses += 1
            elif trend == 'DOWN' and btc_move_pct < 0:
                if winner == 'DOWN':
                    hdo_down_trend_down_wins += 1
                else:
                    hdo_down_trend_down_losses += 1

    print(f"HDO Only, UP Trend & BTC Up - Wins: {hdo_up_trend_up_wins}, Losses: {hdo_up_trend_up_losses}")
    print(f"HDO Only, DOWN Trend & BTC Down - Wins: {hdo_down_trend_down_wins}, Losses: {hdo_down_trend_down_losses}")
    print(f"Total HDO Only Triggers: {total_hdo_triggers}")

except Exception as e:
    print(f'Runtime Error: {e}')
