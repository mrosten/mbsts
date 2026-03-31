import json

def analyze_nitro_neutral():
    try:
        with open('darwin/experiment_log.json', 'r') as f:
            history = json.load(f)

        nitro_neutral_up = 0
        nitro_neutral_down = 0
        total_nitro_neutral = 0

        for item in history:
            mdata = item.get('market_data', {})
            scanners = mdata.get('fired_scanners', [])
            trend = mdata.get('trend_1h', 'NEUTRAL')
            btc_move_pct = mdata.get('btc_move_pct', 0.0)

            if 'Nitro' in scanners and len(scanners) == 1 and trend == 'NEUTRAL':
                total_nitro_neutral += 1
                if btc_move_pct > 0:
                    nitro_neutral_up += 1
                else:
                    nitro_neutral_down += 1

        print(f'Nitro Alone (Neutral Trend) - UP: {nitro_neutral_up}, DOWN: {nitro_neutral_down}, TOTAL: {total_nitro_neutral}')

    except Exception as e:
        print(f'Error: {e}')

analyze_nitro_neutral()
