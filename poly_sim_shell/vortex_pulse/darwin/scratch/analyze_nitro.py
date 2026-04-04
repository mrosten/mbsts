import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    nitro_up_up = 0
    nitro_up_down = 0
    nitro_down_down = 0
    nitro_down_up = 0
    nitro_total = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)

        if 'Nitro' in fired and len(fired) == 1:
            nitro_total += 1
            if trend == 'M-UP':
                if btc_move_pct > 0:
                    nitro_up_up += 1
                else:
                    nitro_up_down += 1
            elif trend == 'M-DOWN':
                if btc_move_pct < 0:
                    nitro_down_down += 1
                else:
                    nitro_down_up += 1

    print(f'Nitro Only, UP Trend & BTC Up - Wins: {nitro_up_up}, Losses: {nitro_up_down}')
    print(f'Nitro Only, DOWN Trend & BTC Down - Wins: {nitro_down_down}, Losses: {nitro_down_up}')
    print(f'Total Nitro Only Triggers: {nitro_total}')

except Exception as e:
    print(f'Runtime Error: {e}')
