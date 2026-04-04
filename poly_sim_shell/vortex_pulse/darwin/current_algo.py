def scan(data):
    fired = data.get('fired_scanners', [])
    trend = data.get('trend_1h', 'NEUTRAL')
    btc_move_pct = data.get('btc_move_pct', 0.0)
    odds_score = data.get('odds_score', 0.0)
    atr_5m = data.get('atr_5m', 0.0)

    if 'Nitro' in fired and len(fired) == 1:
        if trend == 'M-UP':
            return 'BET_UP'
        elif trend == 'M-DOWN':
            return 'BET_DOWN'
        else:
            return 'HOLD'
    else:
        return 'HOLD'