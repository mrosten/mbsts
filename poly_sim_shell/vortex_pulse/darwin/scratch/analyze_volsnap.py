import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    volsnap_up_trend_up_wins = 0
    volsnap_up_trend_up_losses = 0
    volsnap_down_trend_down_wins = 0
    volsnap_down_trend_down_losses = 0
    total_volsnap_triggers = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired_scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        winner = item.get('winner', 'N/A')

        if 'VolSnap' in fired_scanners and len(fired_scanners) == 1:
            total_volsnap_triggers += 1

            if trend == 'UP' and btc_move_pct > 0:
                if winner == 'UP':
                    volsnap_up_trend_up_wins += 1
                else:
                    volsnap_up_trend_up_losses += 1
            elif trend == 'DOWN' and btc_move_pct < 0:
                if winner == 'DOWN':
                    volsnap_down_trend_down_wins += 1
                else:
                    volsnap_down_trend_down_losses += 1

    print(f'VolSnap Only, UP Trend & BTC Up - Wins: {volsnap_up_trend_up_wins}, Losses: {volsnap_up_trend_up_losses}')
    print(f'VolSnap Only, DOWN Trend & BTC Down - Wins: {volsnap_down_trend_down_wins}, Losses: {volsnap_down_trend_down_losses}')
    print(f'Total VolSnap Only Triggers: {total_volsnap_triggers}')

except Exception as e:
    print(f'Runtime Error: {e}')