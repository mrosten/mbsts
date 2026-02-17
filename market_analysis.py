import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime

# API Endpoints
COINCAP_ASSET = "https://api.coincap.io/v2/assets/bitcoin"
COINCAP_HISTORY = "https://api.coincap.io/v2/assets/bitcoin/history"
COINGECKO_PRICE = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
COINGECKO_HISTORY = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
BINANCE_PRICE = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"

def get_current_btc_price_coincap():
    try:
        resp = requests.get(COINCAP_ASSET, timeout=3)
        data = resp.json()
        return float(data['data']['priceUsd'])
    except:
        return None

def get_current_btc_price_binance():
    try:
        resp = requests.get(BINANCE_PRICE, timeout=3)
        data = resp.json()
        return float(data['price'])
    except:
        return None

def get_current_btc_price_coingecko():
    try:
        resp = requests.get(COINGECKO_PRICE, timeout=3)
        data = resp.json()
        return float(data['bitcoin']['usd'])
    except:
        return None

def get_current_btc_price():
    val = get_current_btc_price_coincap()
    if val: return val, "CoinCap"
        
    val = get_current_btc_price_binance()
    if val: return val, "Binance"

    val = get_current_btc_price_coingecko()
    if val: return val, "CoinGecko"
    return None, "Unknown"

def get_historical_btc_price_coincap(timestamp_ms):
    start = timestamp_ms
    end = start + 60000 
    url = f"{COINCAP_HISTORY}?interval=m1&start={start}&end={end}"
    try:
        resp = requests.get(url, timeout=3)
        data = resp.json().get('data', [])
        if data:
            return float(data[0]['priceUsd'])
    except:
        return None

def get_historical_btc_price_binance(timestamp_ms):
    url = f"{BINANCE_KLINES}?symbol=BTCUSDT&interval=1m&startTime={timestamp_ms}&limit=1"
    try:
        resp = requests.get(url, timeout=3)
        data = resp.json()
        if data and len(data) > 0:
            return float(data[0][1])
    except:
        return None

def get_historical_btc_price_coingecko(timestamp_ms):
    start_s = int(timestamp_ms / 1000) - 300 
    end_s = start_s + 600
    url = f"{COINGECKO_HISTORY}?vs_currency=usd&from={start_s}&to={end_s}"
    try:
        resp = requests.get(url, timeout=3)
        data = resp.json()
        prices = data.get('prices', [])
        if prices:
            closest_price = None
            min_diff = float('inf')
            target_ms = timestamp_ms
            for p in prices:
                p_ts = p[0]
                val = p[1]
                diff = abs(p_ts - target_ms)
                if diff < min_diff:
                    min_diff = diff
                    closest_price = val
            return closest_price
    except:
        return None

def get_historical_btc_price(timestamp_ms):
    val = get_historical_btc_price_coincap(timestamp_ms)
    if val: return val, "CoinCap"
        
    val = get_historical_btc_price_binance(timestamp_ms)
    if val: return val, "Binance"

    val = get_historical_btc_price_coingecko(timestamp_ms)
    if val: return val, "CoinGecko"
    return None, "Unknown"

def get_binance_candles_df(limit=200):
    url = f"{BINANCE_KLINES}?symbol=BTCUSDT&interval=15m&limit={limit}"
    try:
        resp = requests.get(url, timeout=3)
        data = resp.json()
        if not isinstance(data, list): return pd.DataFrame()
        
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'q_vol', 'trades', 't_base', 't_quote', 'ignore'])
        cols = ['open', 'high', 'low', 'close', 'volume']
        df[cols] = df[cols].astype(float)
        return df
    except Exception as e:
        print(f"Candle fetch failed: {e}")
        return pd.DataFrame()

# Pure Pandas TA
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def calc_bandwidth(upper, lower, unique_series_for_mean):
    # Bandwidth = (Upper - Lower) / Middle(SMA)
    # This shows volatility relative to price
    middle = unique_series_for_mean
    return ((upper - lower) / middle) * 100

def calc_bbands(series, period=20, std_dev=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, lower

def calc_sma(series, period):
    return series.rolling(window=period).mean()

def calc_supertrend(df, period=10, multiplier=3):
    # Simplified Trend Signal based on SMA and Price Action (Snapshot)
    # Full SuperTrend requires recursive calculation which can be slow in pure python/pandas without loop
    # We will use a robust approximation: 
    # Trend = Bullish if Close > SMA(50) AND Close > SMA(20)
    
    close = df['close']
    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    curr = close.iloc[-1]
    
    if curr > sma20 and curr > sma50:
        return "🟢 BULLISH"
    elif curr < sma20 and curr < sma50:
        return "🔴 BEARISH"
    elif curr > sma50:
        return "🌗 WEAK BULL"
    else:
        return "🌑 WEAK BEAR"

def get_trading_recommendation(price_diff, trend, vol_status, time_left):
    # Logic:
    # 1. If Time is very short (< 3 mins), mostly random/gambling unless huge diff -> Inadvisable
    # 2. If Volatility is High (Expansion), risk of reversal is high -> Inadvisable or Caution
    # 3. If Trend aligns with Winning Side -> Good
    
    # Reasoning list
    reasoning = []
    advice = "N/A"
    
    # Time Check - CONVERGENCE LOGIC
    is_clutch_time = False
    if time_left < 30:
        reasoning.append(f"⏱️ **Time Critical:** < 30s remaining. Execution risk too high. AVOID.")
        return "⛔ TOO LATE (Exec Risk)", " ".join(reasoning)
    elif time_left < 300: # Last 5 minutes
        reasoning.append(f"⏱️ **Convergence Zone:** < 5 mins left. Prices will diverge rapidly to $1.00 or $0.00.")
        is_clutch_time = True
    else:
        reasoning.append(f"⏱️ **Time:** Sufficient time ({int(time_left/60)}m) for trend to play out.")
        
    # Winning Side
    winning_side = "UP" if price_diff > 0 else "DOWN"
    
    # Check Trend Alignment
    trend_aligned = False
    if winning_side == "UP" and ("BULL" in trend): trend_aligned = True
    if winning_side == "DOWN" and ("BEAR" in trend): trend_aligned = True
    
    # Volatility Check
    high_vol = "High" in vol_status
    if high_vol:
        reasoning.append(f"💥 **Volatility:** Market is expanding/volatile. Reversals possible.")
    else:
        reasoning.append(f"💤 **Volatility:** Market is stable/squeezing.")

    if not trend_aligned:
         reasoning.append(f"⚠️ **Trend Divergence:** Price is winning {winning_side} but Trend is {trend}.")

    # RSI Check (Optional integration if passed, but for now just general)
    # We don't have RSI passed here, implying simple logic.
    
    # Final Decision
    if is_clutch_time:
         # In Convergence Zone, being on the winning side is huge
         if abs(price_diff) > 10:
             advice = f"🚀 SNIPE {winning_side} (Convergence Play)"
             reasoning.append(f"**Conclusion:** 🟢 TIME DECAY PLAY. Market is winning {winning_side} near expiry. Probability of reaching $1.00 is high.")
         else:
             advice = "⚠️ CHOPPY / RISKY (Too Close)"
             reasoning.append(f"**Conclusion:** Price is too close to strike for the final minutes. Coin flip.")
             
    elif trend_aligned and not high_vol:
        advice = f"✅ BETTING {winning_side} ODDS LOOK GOOD"
        reasoning.append(f"**Conclusion:** Strong setup. Trend and price agree with stable volatility.")
    elif trend_aligned and high_vol:
        advice = f"⚠️ BETTING {winning_side} POSSIBLE (Caution: High Vol)"
        reasoning.append(f"**Conclusion:** Setup aligns but high volatility increases risk.")
    else:
        advice = "⛔ TRADING INADVISABLE (Trend/Price Divergence)"
        reasoning.append(f"**Conclusion:** Conflicting signals. Best to wait for clarity.")
        
    return advice, " ".join(reasoning)

def analyze_market_data(url):
    # Returns a dictionary of analysis results
    result = {}
    
    # 1. Parse Slug
    try:
        slug = url.strip("/").split("?")[0].split("/")[-1]
        ts_str = slug.split("-")[-1]
        start_ts = int(ts_str)
        end_ts = start_ts + (15 * 60)
        
        result['start_ts'] = start_ts
        result['end_ts'] = end_ts
        
        # Time Left
        now = time.time()
        result['time_left_s'] = max(0, end_ts - now)
    except:
        result['error'] = "Could not parse timestamp from URL"
        return result

    # 2. Prices
    curr_price, curr_src = get_current_btc_price()
    strike_price, strike_src = get_historical_btc_price(start_ts * 1000)
    
    result['current_price'] = curr_price
    result['current_source'] = curr_src
    result['strike_price'] = strike_price
    result['strike_source'] = strike_src
    
    if curr_price and strike_price:
        result['diff'] = curr_price - strike_price
        result['winning'] = "UP" if result['diff'] > 0 else "DOWN"
    
    # 3. TA
    df = get_binance_candles_df(200)
    if not df.empty:
        curr_close = df['close'].iloc[-1]
        
        # RSI
        rsi = calc_rsi(df['close'], 14).iloc[-1]
        rsi_status = "Neutral"
        if rsi > 70: rsi_status = "Overbought 🔴"
        elif rsi < 30: rsi_status = "Oversold 🟢"
        
        result['rsi'] = rsi
        result['rsi_status'] = rsi_status
        
        # BBands
        up, low = calc_bbands(df['close'])
        upper = up.iloc[-1]
        lower = low.iloc[-1]
        sma20 = df['close'].rolling(20).mean().iloc[-1]
        
        bb_status = "Inside"
        if curr_close > upper: bb_status = "Above Upper 🔴"
        elif curr_close < lower: bb_status = "Below Lower 🟢"
        
        result['bb_upper'] = upper
        result['bb_lower'] = lower
        result['bb_status'] = bb_status
        
        # Volatility Metrics
        atr = calc_atr(df, 14).iloc[-1]
        bandwidth = calc_bandwidth(up, low, df['close'].rolling(20).mean()).iloc[-1]
        
        result['atr'] = atr
        result['bandwidth'] = bandwidth
        
        # Interpret Volatility
        # Heuristic: Bandwidth < 1.0 is often a "Squeeze" for BTC 15m (low vol)
        # Bandwidth > 3.0 is high vol
        if bandwidth < 1.0: result['vol_status'] = "Low (Squeeze) 💤"
        elif bandwidth > 3.0: result['vol_status'] = "High (Expansion) 💥"
        else: result['vol_status'] = "Normal"
        
        # SMA
        sma50 = calc_sma(df['close'], 50).iloc[-1]
        result['sma50'] = sma50
        result['sma_status'] = "Above" if curr_close > sma50 else "Below"
        
        # Trend
        result['trend'] = calc_supertrend(df)
        
        # Recommendation
        if 'diff' in result:
             result['recommendation'], result['reasoning'] = get_trading_recommendation(
                result['diff'], result['trend'], result.get('vol_status', 'Normal'), result['time_left_s']
             )
        else:
             result['recommendation'] = "N/A (Missing Price Data)"
        
    return result
