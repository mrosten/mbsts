import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)
    nitro_alone_up = 0
    nitro_alone_down = 0
    total_nitro_alone = 0
    for item in history:
        mdata = item.get('market_data', {})
        fired_scanners = mdata.get('fired_scanners', [])
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        if 'Nitro' in fired_scanners and 'VSN' not in fired_scanners:
            total_nitro_alone += 1
            if btc_move_pct > 0:
                nitro_alone_up += 1
            else:
                nitro_alone_down += 1

    print(f'Nitro alone, BTC Up: {nitro_alone_up}')
    print(f'Nitro alone, BTC Down: {nitro_alone_down}')
    print(f'Total Nitro alone fired: {total_nitro_alone}')

except Exception as e:
    print(f'Runtime Error: {e}')