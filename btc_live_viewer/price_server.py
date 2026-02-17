"""
Price Server for Live BTC Viewer
Fetches real Polymarket prices and serves them via local HTTP API
"""

import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Global price cache
price_cache = {
    'btc': 0,
    'up': 0.50,
    'down': 0.50,
    'upId': None,
    'downId': None,
    'lastUpdate': None,
    'source': 'initializing'
}

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
    last_window = 0
    
    while True:
        try:
            current_window, _ = get_current_window()
            
            # Check for new window
            if current_window != last_window:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] New window: {current_window}")
                price_cache['upId'] = None
                price_cache['downId'] = None
                fetch_market_data()
                last_window = current_window
            
            fetch_btc_price()
            fetch_polymarket_prices()
            
        except Exception as e:
            print(f"Updater error: {e}")
        
        time.sleep(1)

class PriceHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # CORS headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.end_headers()
        
        response = json.dumps(price_cache)
        self.wfile.write(response.encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

def main():
    port = 8082
    
    # Start price updater thread
    updater_thread = threading.Thread(target=price_updater, daemon=True)
    updater_thread.start()
    
    # Start HTTP server
    server = HTTPServer(('localhost', port), PriceHandler)
    print(f"Price server running on http://localhost:{port}")
    print("Fetching real Polymarket prices...")
    print("-" * 50)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

if __name__ == '__main__':
    main()
