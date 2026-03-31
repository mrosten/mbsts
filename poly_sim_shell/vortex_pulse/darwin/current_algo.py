def scan(data):
    fired = data.get('fired_scanners', [])
    trend = data.get('trend_1h', 'NEUTRAL')
    btc_move_pct = data.get('btc_move_pct', 0.0)
    odds_score = data.get('odds_score', 0.0)
    atr_5m = data.get('atr_5m', 0.0)

    if 'Nitro' in fired and 'VolSnap' in fired and len(fired) <= 3:
        # Stricter odds score filter and ATR threshold
        if abs(odds_score) > 80 and atr_5m > 0.01:
            # Check for alignment between BTC move and trend
            if trend == 'UP' or trend == 'N-UP' or trend == 'D-UP':
                if btc_move_pct > 0:
                    return 'BET_UP'
                else:
                    return 'HOLD' #Hold if BTC move is down despite the bullish trend
            elif trend == 'DOWN' or trend == 'N-DOWN' or trend == 'U-DOWN':
                if btc_move_pct < 0:
                    return 'BET_DOWN'
                else:
                    return 'HOLD'
    return 'HOLD'