import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    nitro_vol_hdo_up_up = 0
    nitro_vol_hdo_up_down = 0
    nitro_vol_hdo_down_up = 0
    nitro_vol_hdo_down_down = 0
    total_nitro_vol_hdo_fired = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)

        if 'Nitro' in fired and 'VolSnap' in fired and 'HDO' in fired:
            total_nitro_vol_hdo_fired += 1
            if btc_move_pct > 0:
                if item.get('winner') == 'UP':
                    nitro_vol_hdo_up_up += 1
                else:
                    nitro_vol_hdo_up_down += 1
            else:
                if item.get('winner') == 'DOWN':
                    nitro_vol_hdo_down_down += 1
                else:
                    nitro_vol_hdo_down_up += 1

    print(f'Nitro + VolSnap + HDO, BTC Up - UP: {nitro_vol_hdo_up_up}, DOWN: {nitro_vol_hdo_up_down}')
    print(f'Nitro + VolSnap + HDO, BTC Down - UP: {nitro_vol_hdo_down_up}, DOWN: {nitro_vol_hdo_down_down}')
    print(f'Total Nitro+VolSnap+HDO Fired: {total_nitro_vol_hdo_fired}')

except Exception as e:
    print(f'Runtime Error: {e}')