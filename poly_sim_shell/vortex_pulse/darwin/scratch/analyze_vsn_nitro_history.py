import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    vsn_nitro_s_down_up = 0
    vsn_nitro_s_down_down = 0
    vsn_nitro_s_up_up = 0
    vsn_nitro_s_up_down = 0
    total_vsn_nitro = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'NEUTRAL')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)

        if 'VSN' in fired and 'Nitro' in fired:
            total_vsn_nitro += 1

            if trend == 'S-DOWN':
                if btc_move_pct > 0:
                    vsn_nitro_s_down_up += 1
                else:
                    vsn_nitro_s_down_down += 1

            elif trend == 'S-UP':
                if btc_move_pct > 0:
                    vsn_nitro_s_up_up += 1
                else:
                    vsn_nitro_s_up_down += 1

    print(f'VSN + Nitro S-DOWN, BTC Up: {vsn_nitro_s_down_up}')
    print(f'VSN + Nitro S-DOWN, BTC Down: {vsn_nitro_s_down_down}')
    print(f'VSN + Nitro S-UP, BTC Up: {vsn_nitro_s_up_up}')
    print(f'VSN + Nitro S-UP, BTC Down: {vsn_nitro_s_up_down}')
    print(f'Total VSN+Nitro Fired: {total_vsn_nitro}')

except Exception as e:
    print(f'Error: {e}')