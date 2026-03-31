def scan(data):
    """
    Improved Darwin Algorithm - More flexible trading logic
    """
    fired = data.get('fired_scanners', [])
    trend = data.get('trend_1h', 'NEUTRAL')
    btc_move_pct = data.get('btc_move_pct', 0.0)
    odds_score = data.get('odds_score', 0.0)
    atr_5m = data.get('atr_5m', 0.0)
    
    # More flexible conditions - not limited to exactly 1 scanner
    if len(fired) >= 1:
        # Check for VolSnap (volatility breakout) pattern
        if 'VolSnap' in fired:
            # Strong downward move with negative odds
            if btc_move_pct < -0.01 and odds_score < -10:
                return 'BET_DOWN'
            # Strong upward move with positive odds
            elif btc_move_pct > 0.01 and odds_score > 10:
                return 'BET_UP'
        
        # Check for Nitro (momentum) pattern
        if 'Nitro' in fired:
            # Downward momentum
            if trend == 'DOWN' and btc_move_pct < -0.005:
                return 'BET_DOWN'
            # Upward momentum
            elif trend == 'UP' and btc_move_pct > 0.005:
                return 'BET_UP'
        
        # Multiple scanners confirming same direction
        up_scanners = [s for s in fired if 'MOM' in s or 'MM2' in s or 'NIT' in s]
        down_scanners = [s for s in fired if 'TRA' in s or 'FAK' in s or 'RSI' in s]
        
        if len(up_scanners) >= 2 and trend == 'UP' and btc_move_pct > 0.005:
            return 'BET_UP'
        elif len(down_scanners) >= 2 and trend == 'DOWN' and btc_move_pct < -0.005:
            return 'BET_DOWN'
    
    return 'HOLD'
