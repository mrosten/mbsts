import json

trend_align_wins = 0
trend_align_losses = 0
total_briefing_triggers = 0

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)
    for item in history:
        mdata = item.get('market_data', {})
        scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        odds_score = mdata.get('odds_score', 0.0)
        tilt_dir = mdata.get('tilt_dir', 'NONE')

        if 'Briefing' in scanners and len(scanners) == 1 and abs(odds_score) > 90:
            total_briefing_triggers += 1
            if trend == 'UP' and btc_move_pct > 0 and tilt_dir == 'UP':
                trend_align_wins += 1
            elif trend == 'DOWN' and btc_move_pct < 0 and tilt_dir == 'DOWN':
                trend_align_wins += 1
            elif trend == 'UP' and btc_move_pct < 0 and tilt_dir == 'UP':
                trend_align_losses += 1
            elif trend == 'DOWN' and btc_move_pct > 0 and tilt_dir == 'DOWN':
                trend_align_losses += 1
            else:
                trend_align_losses += 1 # consider cases where trend or BTC move is neutral

    print(f"Briefing, UP Trend & BTC Up - Wins: {trend_align_wins}, Losses: {trend_align_losses}\nBriefing, DOWN Trend & BTC Down - Wins: {trend_align_wins}, Losses: {trend_align_losses}\nTotal Briefing Triggers: {total_briefing_triggers}")

except Exception as e:
    print(f'Runtime Error: {e}')