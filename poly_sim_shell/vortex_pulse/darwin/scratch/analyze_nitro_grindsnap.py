import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)
    
    nitro_grindsnap_up_up = 0
    nitro_grindsnap_up_down = 0
    nitro_grindsnap_down_up = 0
    nitro_grindsnap_down_down = 0
    
    total_nitro_grindsnap = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired = mdata.get('fired_scanners', [])
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        
        if 'Nitro' in fired and 'GrindSnap' in fired and len(fired) == 2:
            total_nitro_grindsnap += 1
            if btc_move_pct > 0:
                if item.get('winner') == 'UP':
                    nitro_grindsnap_up_up += 1
                else:
                    nitro_grindsnap_up_down += 1
            else:
                if item.get('winner') == 'UP':
                    nitro_grindsnap_down_up += 1
                else:
                    nitro_grindsnap_down_down += 1

    print(f'Nitro + GrindSnap, BTC Up - UP: {nitro_grindsnap_up_up}, DOWN: {nitro_grindsnap_up_down}')
    print(f'Nitro + GrindSnap, BTC Down - UP: {nitro_grindsnap_down_up}, DOWN: {nitro_grindsnap_down_down}')
    print(f'Total Nitro+GrindSnap Fired: {total_nitro_grindsnap}')

except Exception as e:
    print(f'Runtime Error: {e}')