import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    wcp_up_wins = 0
    wcp_up_losses = 0
    wcp_down_wins = 0
    wcp_down_losses = 0
    wcp_total_triggers = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired_scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'NEUTRAL')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        winner = item.get('winner', 'N/A')

        if 'WCP' in fired_scanners:
            wcp_total_triggers += 1
            if trend == 'UP':
                if btc_move_pct > 0 and winner == 'UP':
                    wcp_up_wins += 1
                elif btc_move_pct > 0 and winner == 'DOWN':
                    wcp_up_losses += 1
            elif trend == 'DOWN':
                if btc_move_pct < 0 and winner == 'DOWN':
                    wcp_down_wins += 1
                elif btc_move_pct < 0 and winner == 'UP':
                    wcp_down_losses += 1

    print(f'WCP Only, UP Trend & BTC Up - Wins: {wcp_up_wins}, Losses: {wcp_up_losses}')
    print(f'WCP Only, DOWN Trend & BTC Down - Wins: {wcp_down_wins}, Losses: {wcp_down_losses}')
    print(f'Total WCP Only Triggers: {wcp_total_triggers}')

except Exception as e:
    print(f'Runtime Error: {e}')