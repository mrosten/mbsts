import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    nitro_neutral_up = 0
    nitro_neutral_down = 0
    nitro_neutral_total = 0

    for item in history:
        mdata = item.get('market_data', {})
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        fired = mdata.get('fired_scanners', [])

        if 'Nitro' in fired and len(fired) == 1 and trend == 'NEUTRAL':
            nitro_neutral_total += 1
            if btc_move_pct > 0:
                nitro_neutral_up += 1
            else:
                nitro_neutral_down += 1

    print(f'Nitro Alone (Neutral Trend) - UP: {nitro_neutral_up}, DOWN: {nitro_neutral_down}, TOTAL: {nitro_neutral_total}')

except Exception as e:
    print(f'Error: {e}')