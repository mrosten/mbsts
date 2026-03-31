import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    vsn_up_wins = 0
    vsn_up_losses = 0
    vsn_down_wins = 0
    vsn_down_losses = 0
    total_vsn_firings = 0

    for item in history:
        mdata = item.get('market_data', {})
        scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'NEUTRAL')
        outcome = item.get('outcome', 'N/A')
        odds_score = mdata.get('odds_score', 0.0)
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        atr_5m = mdata.get('atr_5m', 0.0)

        if 'VSN' in scanners and len(scanners) == 1:
            total_vsn_firings += 1
            if trend in ['DOWN', 'M-DOWN', 'S-DOWN']:
                if odds_score > -50 and btc_move_pct < -1.5 * atr_5m: # Same condition as current algo
                    if outcome == 'UP':
                        vsn_up_wins += 1
                    elif outcome == 'DOWN':
                        vsn_up_losses += 1
            elif trend in ['UP', 'M-UP', 'S-UP']:
                if odds_score < 50 and btc_move_pct > 1.5 * atr_5m: # Same condition as current algo
                    if outcome == 'DOWN':
                        vsn_down_wins += 1
                    elif outcome == 'UP':
                        vsn_down_losses += 1
    print(f'Total VSN firings: {total_vsn_firings}')
    print(f'VSN UP wins: {vsn_up_wins}, losses: {vsn_up_losses}')
    print(f'VSN DOWN wins: {vsn_down_wins}, losses: {vsn_down_losses}')

except Exception as e:
    print(f'Runtime Error: {e}')