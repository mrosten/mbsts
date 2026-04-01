import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    nitro_volsnap_up_trend_up = 0
    nitro_volsnap_up_trend_down = 0
    nitro_volsnap_down_trend_up = 0
    nitro_volsnap_down_trend_down = 0
    
    total_nitro_volsnap = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)

        if 'Nitro' in fired and 'VolSnap' in fired and len(fired) == 2:
            total_nitro_volsnap += 1
            if trend == 'UP' or trend == 'S-UP':
                if btc_move_pct > 0:
                    nitro_volsnap_up_trend_up += 1
                else:
                    nitro_volsnap_up_trend_down += 1
            elif trend == 'DOWN' or trend == 'S-DOWN':
                if btc_move_pct > 0:
                    nitro_volsnap_down_trend_up += 1
                else:
                    nitro_volsnap_down_trend_down += 1
                    
    print(f"Nitro + VolSnap, UP Trend & BTC Up - {nitro_volsnap_up_trend_up}\n")
    print(f"Nitro + VolSnap, UP Trend & BTC Down - {nitro_volsnap_up_trend_down}\n")
    print(f"Nitro + VolSnap, DOWN Trend & BTC Up - {nitro_volsnap_down_trend_up}\n")
    print(f"Nitro + VolSnap, DOWN Trend & BTC Down - {nitro_volsnap_down_trend_down}\n")
    print(f"Total Nitro+VolSnap Fired: {total_nitro_volsnap}")

except Exception as e:
    print(f'Runtime Error: {e}')