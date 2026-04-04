import json

try:
    with open('darwin/experiment_log.json', 'r') as f:
        history = json.load(f)

    hdo_up_trend_up = 0
    hdo_up_trend_down = 0
    hdo_down_trend_down = 0
    hdo_down_trend_up = 0

    total_hdo_triggers = 0

    for item in history:
        mdata = item.get('market_data', {})
        fired_scanners = mdata.get('fired_scanners', [])
        trend = mdata.get('trend_1h', 'N/A')
        btc_move_pct = mdata.get('btc_move_pct', 0.0)
        
        if 'HDO' in fired_scanners and len(fired_scanners) == 1:
            total_hdo_triggers += 1
            if trend == 'UP':
                if btc_move_pct > 0:
                    hdo_up_trend_up += 1
                else:
                    hdo_up_trend_down += 1
            elif trend == 'DOWN':
                if btc_move_pct < 0:
                    hdo_down_trend_down += 1
                else:
                    hdo_down_trend_up += 1

    print(f'HDO Only, UP Trend & BTC Up - Wins: {hdo_up_trend_up}, Losses: {hdo_up_trend_down}')
    print(f'HDO Only, DOWN Trend & BTC Down - Wins: {hdo_down_trend_down}, Losses: {hdo_down_trend_up}')
    print(f'Total HDO Only Triggers: {total_hdo_triggers}')

except Exception as e:
    print(f'Runtime Error: {e}')
