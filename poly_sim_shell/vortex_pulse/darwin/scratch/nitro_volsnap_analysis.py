import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    nitro_volsnap_up_up = 0
    nitro_volsnap_up_down = 0
    nitro_volsnap_down_up = 0
    nitro_volsnap_down_down = 0
    total_nitro_volsnap = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        winner = item.get('winner', 'N/A')
        trend = mdata.get('trend_1h', 'NEUTRAL')

        if 'Nitro' in fired and 'VolSnap' in fired and len(fired) == 2:
            total_nitro_volsnap += 1
            if btc_move_pct > 0:
                if winner == 'UP':
                    nitro_volsnap_up_up += 1
                else:
                    nitro_volsnap_up_down += 1
            else:
                if winner == 'DOWN':
                    nitro_volsnap_down_down += 1
                else:
                    nitro_volsnap_down_up += 1

    print(f"Nitro + VolSnap, BTC Up - UP: {nitro_volsnap_up_up}, DOWN: {nitro_volsnap_up_down}")
    print(f"Nitro + VolSnap, BTC Down - UP: {nitro_volsnap_down_up}, DOWN: {nitro_volsnap_down_down}")
    print(f"Total Nitro+VolSnap Fired: {total_nitro_volsnap}")

except Exception as e:
    print(f'Runtime Error: {e}')