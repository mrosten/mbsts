"""
Combined Web + Price Server for Live BTC Viewer
Serves both the webpage AND fetches real Polymarket prices
Run with: python server.py
Then open: http://localhost:8081
"""

import json
import time
import threading
import os
from flask import Flask, send_from_directory, jsonify
from urllib.request import urlopen, Request
from datetime import datetime

app = Flask(__name__, static_folder='.')

# Global price cache
price_cache = {
    'btc': 0,
    'up': 0.50,
    'down': 0.50,
    'upId': None,
    'downId': None,
    'lastUpdate': None,
    'source': 'initializing',
    'signals': {}
}

# Price history for current window (server-side storage)
price_history = []
current_window_start = 0

class NPatternScanner:
    def __init__(self):
        # SETTINGS
        self.min_impulse_size = 0.0003  # First move must be at least 0.03%
        self.max_retrace_depth = 0.80   # Dip cannot lose more than 80% of gain
        self.support_tolerance = 0.0001 # How close to Open/MA counts as a "Test"?
        
    def analyze(self, history_objs, open_price):
        """
        Analyzes 1-second tick history to find N-Pattern
        Returns: "WAIT", "BET_UP_CONFIRMED", or "PATTERN_INVALID"
        """
        if not history_objs:
            return "WAIT"

        # 1. PREPARE DATA relative to elapsed time
        # We need to look at specific time windows.
        # Phase 1: Minutes 0-3 (0 to 180s)
        phase1_prices = [p['price'] for p in history_objs if p['elapsed'] <= 180]
        
        if not phase1_prices:
            return "WAIT"
            
        # 1. IDENTIFY PHASE 1: THE IMPULSE
        first_peak = max(phase1_prices)
        impulse_height = first_peak - open_price
        
        # Filter: Is the first move big enough?
        if impulse_height < (open_price * self.min_impulse_size):
            return "WAIT" # Too small
            
        # 2. IDENTIFY PHASE 2: THE DEFENSE (Minutes 3-6 or just AFTER peak)
        # Find the lowest low AFTER the peak
        # We look at all prices after the peak occurrence
        # Find the index of the first peak occurrence
        peak_idx = next(i for i, p in enumerate(history_objs) if p['price'] == first_peak)
        retrace_objs = history_objs[peak_idx:]
        
        if not retrace_objs:
            return "WAIT"
            
        retrace_prices = [p['price'] for p in retrace_objs]
        retest_low = min(retrace_prices)
        
        # Check A: Did we hold support?
        failed_support = retest_low < (open_price - self.support_tolerance)
        
        # Check B: Did we retrace enough?
        retrace_pct = (first_peak - retest_low) / impulse_height if impulse_height > 0 else 0
        valid_dip = 0.20 <= retrace_pct <= self.max_retrace_depth
        
        if failed_support:
            return "PATTERN_INVALID"
            
        if not valid_dip:
            # We are still waiting for a valid dip, OR we just haven't dipped enough yet.
            # But wait, if we are effectively past the point of dipping... 
            # The pattern says "WAIT" if not dipped enough.
            # But if we are breaking out WITHOUT dipping, it's not this pattern.
            return "WAIT"
            
        # 3. IDENTIFY PHASE 3: THE TRIGGER
        current_price = history_objs[-1]['price']
        
        # The Signal: Price crosses ABOVE the First Peak
        breakout = current_price > first_peak
        
        if breakout and valid_dip:
            return "BET_UP_CONFIRMED"
            
        return "WAIT"

scanner = NPatternScanner()

def get_current_window():
    """Get current 15-minute window timestamps"""
    now = datetime.now()
    min15 = (now.minute // 15) * 15
    window_start = now.replace(minute=min15, second=0, microsecond=0)
    start_ts = int(window_start.timestamp())
    end_ts = start_ts + 900
    return start_ts, end_ts

def fetch_market_data():
    """Fetch Polymarket token IDs for current window"""
    global price_cache
    
    try:
        start_ts, _ = get_current_window()
        slug = f"btc-updown-15m-{start_ts}"
        url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
        
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
        
        if data and 'clobTokenIds' in data:
            ids = data['clobTokenIds']
            if isinstance(ids, str):
                ids = json.loads(ids)
            
            outcomes = data.get('outcomes', [])
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            
            up_id = ids[0]
            down_id = ids[1] if len(ids) > 1 else None
            
            # Map by outcome name
            for i, name in enumerate(outcomes):
                if 'Up' in name or 'Yes' in name:
                    up_id = ids[i]
                elif 'Down' in name or 'No' in name:
                    down_id = ids[i]
            
            price_cache['upId'] = up_id
            price_cache['downId'] = down_id
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Market loaded: {slug}")
            return True
            
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Market fetch failed: {e}")
    
    return False

def fetch_polymarket_prices():
    """Fetch current Polymarket prices"""
    global price_cache
    
    if not price_cache['upId'] or not price_cache['downId']:
        fetch_market_data()
    
    if not price_cache['upId'] or not price_cache['downId']:
        price_cache['source'] = 'no_market'
        return
    
    try:
        # Fetch UP price
        up_url = f"https://clob.polymarket.com/price?token_id={price_cache['upId']}&side=buy"
        req = Request(up_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=3) as response:
            up_data = json.loads(response.read().decode())
            price_cache['up'] = float(up_data.get('price', 0.50))
        
        # Fetch DOWN price
        down_url = f"https://clob.polymarket.com/price?token_id={price_cache['downId']}&side=buy"
        req = Request(down_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=3) as response:
            down_data = json.loads(response.read().decode())
            price_cache['down'] = float(down_data.get('price', 0.50))
        
        price_cache['lastUpdate'] = datetime.now().isoformat()
        price_cache['source'] = 'polymarket'
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Prices: UP=${price_cache['up']:.2f} DOWN=${price_cache['down']:.2f}")
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Price fetch failed: {e}")
        price_cache['source'] = 'error'

def fetch_btc_price():
    """Fetch BTC price from Binance"""
    global price_cache
    
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            price_cache['btc'] = float(data['price'])
    except Exception as e:
        print(f"BTC price fetch failed: {e}")

def price_updater():
    """Background thread to update prices"""
    global price_history, current_window_start
    last_window = 0
    
    while True:
        try:
            window_start, _ = get_current_window()
            
            # Check for new window
            if window_start != last_window:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] New window: {window_start}")
                price_cache['upId'] = None
                price_cache['downId'] = None
                # Clear history for new window
                price_history = []
                current_window_start = window_start
                fetch_market_data()
                last_window = window_start
            
            fetch_btc_price()
            fetch_polymarket_prices()
            
            # Store in history (every update)
            if price_cache['btc'] > 0:
                now = time.time()
                elapsed = int(now - window_start)
                price_history.append({
                    'timestamp': now,
                    'elapsed': elapsed,
                    'price': price_cache['btc'],
                    'up': price_cache['up'],
                    'down': price_cache['down']
                })
                
                # Run Algorithms
                if len(price_history) > 0:
                    open_price = price_history[0]['price']
                    # Ensure signals dict exists
                    if 'signals' not in price_cache:
                        price_cache['signals'] = {}
                        
                    result = scanner.analyze(price_history, open_price)
                    price_cache['signals']['n_pattern'] = result
            
        except Exception as e:
            print(f"Updater error: {e}")
        
        time.sleep(1)


# Routes
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/prices')
def get_prices():
    return jsonify(price_cache)

@app.route('/api/history')
def get_history():
    """Return full price history for current window"""
    window_start, window_end = get_current_window()
    return jsonify({
        'windowStart': window_start,
        'windowEnd': window_end,
        'history': price_history,
        'currentPrice': price_cache
    })

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    print("=" * 50)
    print("Live BTC + Polymarket Viewer")
    print("=" * 50)
    
    # Start price updater thread
    updater_thread = threading.Thread(target=price_updater, daemon=True)
    updater_thread.start()
    
    print("Starting server on http://localhost:8085")
    print("Fetching real Polymarket prices...")
    print("-" * 50)
    
    # Run Flask
    app.run(host='0.0.0.0', port=8085, debug=False, threaded=True)
