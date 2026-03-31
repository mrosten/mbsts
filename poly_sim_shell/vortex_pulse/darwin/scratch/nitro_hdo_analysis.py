import json

def analyze_nitro_hdo():
    try:
        with open('darwin/experiment_log.json', 'r') as f:
            history = json.load(f)

        nitro_hdo_up_up = 0
        nitro_hdo_up_down = 0
        nitro_hdo_down_up = 0
        nitro_hdo_down_down = 0
        total_nitro_hdo = 0

        for item in history:
            mdata = item.get('market_data', {})
            fired = mdata.get('fired_scanners', [])
            btc_move_pct = mdata.get('btc_move_pct', 0.0)

            if 'Nitro' in fired and 'HDO' in fired and len(fired) == 2:
                total_nitro_hdo += 1
                if btc_move_pct > 0:
                    if item.get('winner') == 'UP':
                        nitro_hdo_up_up += 1
                    else:
                        nitro_hdo_up_down += 1
                else:
                    if item.get('winner') == 'UP':
                        nitro_hdo_down_up += 1
                    else:
                        nitro_hdo_down_down += 1

        print(f'Nitro + HDO, BTC Up - UP: {nitro_hdo_up_up}, DOWN: {nitro_hdo_up_down}')
        print(f'Nitro + HDO, BTC Down - UP: {nitro_hdo_down_up}, DOWN: {nitro_hdo_down_down}')
        print(f'Total Nitro+HDO Fired: {total_nitro_hdo}')

    except Exception as e:
        print(f'Error analyzing Nitro+HDO data: {e}')


analyze_nitro_hdo()
