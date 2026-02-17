
def check_reversion(analysis_results):
    """
    Reversion Master Strategy:
    - Best for Low Volatility (Bandwidth < 1.0) or Normal.
    - Buy UP if Price <= BB Lower AND RSI < 30 (Oversold).
    - Buy DOWN if Price >= BB Upper AND RSI > 70 (Overbought).
    """
    if not analysis_results: return None
    
    # 1. Bandwidth Check (Avoid High Volatility Expansion)
    bandwidth = analysis_results.get('bandwidth', 100)
    if bandwidth > 3.0: 
        return None # Too volatile for reversion
        
    rsi = analysis_results.get('rsi', 50)
    curr_price = analysis_results.get('current_price', 0)
    bb_upper = analysis_results.get('bb_upper', 0)
    bb_lower = analysis_results.get('bb_lower', 0)
    
    if curr_price == 0: return None
    
    # Buy UP Signal
    if curr_price <= bb_lower and rsi < 30:
        return "UP"
        
    # Buy DOWN Signal
    if curr_price >= bb_upper and rsi > 70:
        return "DOWN"
        
    return None

def check_trend_surfer(analysis_results):
    """
    Trend Surfer Strategy:
    - Best for High Volatility (Bandwidth > 3.0) or Strong Trend.
    - Buy UP if SuperTrend is BULLISH.
    - Buy DOWN if SuperTrend is BEARISH.
    - Ignore RSI (Overbought/Oversold is common in trends).
    """
    if not analysis_results: return None
    
    # 1. Logic
    trend = analysis_results.get('trend', 'N/A')
    
    # Filter: Only trade if Bandwidth is decent (not super squeezed) or if Trend is strong?
    # For now, pure Trend following
    
    if "BULLISH" in trend:
        return "UP"
    elif "BEARISH" in trend:
        return "DOWN"
        
    return None

def calculate_bracket_orders(entry_price, side, tp_pct=0.20, sl_pct=0.10):
    """
    Bracket Bot Logic:
    - Calculates Take Profit and Stop Loss prices based on entry.
    """
    tp_price = 0.0
    sl_price = 0.0
    
    # Polymarket Price Constraints: 0.01 to 0.99
    
    # If we BOUGHT UP:
    # Profit if Price goes UP. Loss if Price goes DOWN.
    # TP = Entry * (1 + tp_pct)
    # SL = Entry * (1 - sl_pct)
    if side.upper() == "UP":
        tp_price = min(0.99, round(entry_price * (1 + tp_pct), 2))
        sl_price = max(0.01, round(entry_price * (1 - sl_pct), 2))
        
    # If we BOUGHT DOWN (Buying "No" shares):
    # This logic depends on if we are shorting or buying "No".
    # In Polymarket, buying "No" is just buying the "Down" token.
    # Price goes UP -> Good for us. Price goes DOWN -> Bad.
    # Wait, "Down" token price ranges 0-1. 
    # If "Down" token is $0.60, it means probability of No is 60%.
    # If event outcome is No, token goes to $1.00.
    # So logic is SAME as UP. Buy Low, Sell High.
    else:
        tp_price = min(0.99, round(entry_price * (1 + tp_pct), 2))
        sl_price = max(0.01, round(entry_price * (1 - sl_pct), 2))
        
    return tp_price, sl_price
