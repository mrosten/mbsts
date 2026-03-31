import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    vsn_nitro_sdown_up = 0
    vsn_nitro_sdown_down = 0
    vsn_nitro_sup_up = 0
    vsn_nitro_sup_down = 0
    total_fired = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'NEUTRAL')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)

        if 'VSN' in fired and 'Nitro' in fired:
            total_fired += 1
            if trend == 'S-DOWN':
                if btc_move_pct > 0:
                    vsn_nitro_sdown_up += 1
                else:
                    vsn_nitro_sdown_down += 1
            elif trend == 'S-UP':
                if btc_move_pct > 0:
                    vsn_nitro_sup_up += 1
                else:
                    vsn_nitro_sup_down += 1

    print(f'VSN + Nitro S-DOWN, BTC Up: {vsn_nitro_sdown_up}')
    print(f'VSN + Nitro S-DOWN, BTC Down: {vsn_nitro_sdown_down}')
    print(f'VSN + Nitro S-UP, BTC Up: {vsn_nitro_sup_up}')
    print(f'VSN + Nitro S-UP, BTC Down: {vsn_nitro_sup_down}')
    print(f'Total VSN+Nitro Fired: {total_fired}')

except Exception as e:
    print(f'Runtime Error: {e}')