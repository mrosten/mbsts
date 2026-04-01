def scan(data):
    fired = data.get('fired_scanners', [])
    trend = data.get('trend_1h', 'NEUTRAL')
    btc_move_pct = data.get('btc_move_pct', 0.0)
    odds_score = data.get('odds_score', 0.0)
    atr_5m = data.get('atr_5m', 0.0)

    if 'Nitro' in fired and 'Briefing' in fired and len(fired) == 2:
        # Stricter odds score filter and higher ATR threshold, requiring stronger trend alignment
        if abs(odds_score) > 95:
            # Require strong alignment between BTC move and trend
            if trend == 'UP' and btc_move_pct > 0 and atr_5m > 0.003:
                return 'BET_UP'
            elif trend == 'DOWN' and btc_move_pct < 0 and atr_5m > 0.003:
                return 'BET_DOWN'
            else:
                return 'HOLD' # Hold if trend alignment is weak
    return 'HOLD'