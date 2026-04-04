import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    nitro_briefing_up_wins = 0
    nitro_briefing_up_losses = 0
    nitro_briefing_down_wins = 0
    nitro_briefing_down_losses = 0
    total_nitro_briefing_triggers = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'NEUTRAL')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        winner = item.get('winner', 'N/A')

        if 'Nitro' in fired and 'Briefing' in fired and len(fired) == 2:
            total_nitro_briefing_triggers += 1
            if trend == 'UP':
                if btc_move_pct > 0:
                    if winner == 'UP':
                        nitro_briefing_up_wins += 1
                    else:
                        nitro_briefing_up_losses += 1
                else:
                    pass # Do not count
            elif trend == 'DOWN':
                if btc_move_pct < 0:
                    if winner == 'DOWN':
                        nitro_briefing_down_wins += 1
                    else:
                        nitro_briefing_down_losses += 1
                else:
                    pass # Do not count

    print(f'Nitro + Briefing, UP Trend & BTC Up - Wins: {nitro_briefing_up_wins}, Losses: {nitro_briefing_up_losses}')
    print(f'Nitro + Briefing, DOWN Trend & BTC Down - Wins: {nitro_briefing_down_wins}, Losses: {nitro_briefing_down_losses}')
    print(f'Total Nitro+Briefing Triggers: {total_nitro_briefing_triggers}')

except Exception as e:
    print(f'Runtime Error: {e}')