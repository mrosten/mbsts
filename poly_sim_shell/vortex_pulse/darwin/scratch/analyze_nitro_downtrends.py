import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    nitro_downtrend_wins = 0
    nitro_downtrend_losses = 0
    total_nitro_downtrend = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'NEUTRAL')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        odds_score = mdata.get('odds_score', 0.0)
        if 'NIT' in fired and 'HDO' not in fired and 'BRI' not in fired and len(fired) == 1 and trend in ['DOWN', 'M-DOWN', 'S-DOWN']:
            total_nitro_downtrend += 1
            if item.get('winner') == 'UP':
                nitro_downtrend_wins += 1
            elif item.get('winner') == 'DOWN':
                nitro_downtrend_losses += 1

    print(f'Nitro alone, trend down:\nUP predictions: Wins={nitro_downtrend_wins}, Losses={nitro_downtrend_losses}\nTotal: {total_nitro_downtrend}')

except Exception as e:
    print(f'Runtime Error: {e}')
