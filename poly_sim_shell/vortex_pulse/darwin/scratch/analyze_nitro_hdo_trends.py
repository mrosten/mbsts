import json

trend_data = {}

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    for item in history:
        mdata = item.get('market_data', {})
        scanners = item.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'NEUTRAL')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        result = item.get('result', 'N/A')

        if 'Nitro' in scanners and 'HDO' in scanners and len(scanners) == 2:
            if trend not in trend_data:
                trend_data[trend] = {
                    'UP': {'wins': 0, 'losses': 0},
                    'DOWN': {'wins': 0, 'losses': 0},
                    'TOTAL': 0
                }

            trend_data[trend]['TOTAL'] += 1

            if btc_move_pct > 0:
                direction = 'UP'
            else:
                direction = 'DOWN'

            if result == 'UP':
                trend_data[trend][direction]['wins'] += 1
            elif result == 'DOWN':
                trend_data[trend][direction]['losses'] += 1


    for trend, data in trend_data.items():
        print(f'Trend: {trend}')
        print(f'  UP Prediction, BTC Up: {data['UP']['wins']}')
        print(f'  UP Prediction, BTC Down: {data['UP']['losses']}')
        print(f'  DOWN Prediction, BTC Up: {data['DOWN']['wins']}')
        print(f'  DOWN Prediction, BTC Down: {data['DOWN']['losses']}')
        print(f'  TOTAL Fired: {data['TOTAL']}')

except Exception as e:
    print(f'Runtime Error: {e}')
