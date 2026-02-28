import time
import requests
import json
import asyncio
import threading
import websockets
from .config import TradingConfig

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    up = sum(d for d in deltas[:period] if d > 0) / period
    down = sum(-d for d in deltas[:period] if d < 0) / period
    if down == 0: return 100
    for i in range(period, len(deltas)):
        d = deltas[i]; g = d if d > 0 else 0; l = -d if d < 0 else 0
        up = (up * (period - 1) + g) / period; down = (down * (period - 1) + l) / period
    if down == 0: return 100
    return 100 - (100 / (1 + up/down))

def calculate_bb(prices, period=20):
    if len(prices) < period: return 0, 0, 0
    slice_ = prices[-period:]; sma = sum(slice_) / period
    std = (sum((x - sma) ** 2 for x in slice_) / period) ** 0.5
    return sma + (std*2), sma, sma - (std*2)

class MarketDataManager:
    def __init__(self, logger_func=None):
        self.logger = logger_func if logger_func else print
        self.market_data = {
            "btc_price": 0, "btc_open": 0, "start_ts": 0, 
            "up_p": 0.5, "down_p": 0.5, "up_price": 0.5, "down_price": 0.5,
            "up_bid": 0.5, "down_bid": 0.5, "up_ask": 0.51, "down_ask": 0.51,
            "up_id": None, "down_id": None,
            "sling_signal": "WAIT", "poly_signal": "N/A", "cobra_signal": "WAIT", 
            "flag_signal": "WAIT", "to_signal": "N/A", "master_score": 0, "master_status": "NEUTRAL",
            "trend_score": 3, "trend_prob": 0.5, "btc_odds": 0, "btc_dyn_rng": 0
        }
        self.chainlink_contract = None
        self.price_history = []
        self.trend_4h = "NEUTRAL"
        self.last_4h_update = 0
        self.first_update = True
        
        # Live WebSocket Price variables
        self.live_price = 0.0
        self.last_ws_update = 0
        self.ws_thread = threading.Thread(target=self._start_ws_thread, daemon=True)
        self.ws_thread.start()
        
    def _start_ws_thread(self):
        """Initializes a new event loop for the background WebSocket connection."""
        time.sleep(1) # Allow Textual UI time to mount before processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._kraken_ws_loop())

    async def _kraken_ws_loop(self):
        """Maintains a continuous WebSocket connection to Kraken for real-time BTC/USD pricing."""
        uri = "wss://ws.kraken.com/"
        while True:
            try:
                self.log("[cyan]Connecting to Kraken WebSocket...[/]")
                async with websockets.connect(uri) as ws:
                    self.log("[green]Kraken WebSocket Connected.[/]")
                    subscribe_message = {
                        "event": "subscribe",
                        "pair": ["XBT/USD"],
                        "subscription": {"name": "ticker"}
                    }
                    await ws.send(json.dumps(subscribe_message))

                    while True:
                        response = await ws.recv()
                        data = json.loads(response)
                        
                        if isinstance(data, list) and len(data) > 1 and 'ticker' in data:
                            ticker_payload = data[1]
                            if 'c' in ticker_payload:
                                self.live_price = float(ticker_payload['c'][0])
                                self.last_ws_update = time.time()
            except Exception as e:
                self.log(f"[yellow]Kraken WS Disconnected: {e}. Reconnecting in 3s...[/]")
                await asyncio.sleep(3)

    def log(self, msg):
        try:
            if self.logger:
                self.logger(msg)
        except Exception:
            pass # Failsafe if the UI thread is not ready to receive logs

    def update_4h_trend(self):
        if (time.time() - self.last_4h_update) < 900: return
        try:
            r = requests.get("https://api.binance.com/api/v3/klines", params={"symbol":"BTCUSDT","interval":"4h","limit":10}, timeout=3)
            r.raise_for_status()
            data = r.json()
            closes = [float(x[4]) for x in data]
            short = sum(closes[-3:]) / 3; long_ = sum(closes) / len(closes)
            self.trend_4h = "UP" if short > long_ * 1.002 else ("DOWN" if short < long_ * 0.998 else "NEUTRAL")
            self.last_4h_update = time.time()
        except requests.RequestException as e:
            self.log(f"[yellow]Warn: 4H Trend Update Failed: {e}[/]")
        except Exception as e:
            self.log(f"[red]Error: 4H Trend Calc Error: {e}[/]")

    def fetch_candles_60m(self):
        try:
            r = requests.get("https://api.binance.com/api/v3/klines", params={"symbol":"BTCUSDT","interval":"1m","limit":200}, timeout=3)
            r.raise_for_status()
            data = r.json()
            return [float(x[4]) for x in data], [float(x[3]) for x in data], [float(x[2]) for x in data], data
        except Exception as e:
            self.log(f"[yellow]Warn: candles Fetch Failed: {e}[/]")
            return [], [], [], []

    def fetch_current_price(self):
        last_known = self.market_data.get("btc_price", 0)

        def _plausible(price):
            """Returns True if price is reasonable relative to last known. Always True if no baseline."""
            if last_known <= 0 or price <= 0:
                return price > 0
            return abs(price - last_known) / last_known < 0.05 # Reject if >5% from last known

        # 1. Primary: Live Kraken WebSocket Price (Must be fresh < 5 seconds)
        if self.live_price > 0 and (time.time() - self.last_ws_update) < 5:
            if _plausible(self.live_price):
                return self.live_price
            else:
                pass  # BTC Sanity: WS price rejected silently

        # 2. Secondary: Chainlink Oracle Backup
        if self.chainlink_contract:
            try:
                raw = self.chainlink_contract.functions.latestAnswer().call()
                price = float(raw) / 10**8
                if _plausible(price):
                    return price
                else:
                    pass  # BTC Sanity: Chainlink price rejected silently
            except: pass

        # 3. Tertiary: Binance REST Fallback
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=2).json()
            price = float(r['price'])
            if _plausible(price):
                return price
            else:
                pass  # BTC Sanity: Binance price rejected silently
        except Exception: pass

        # 4. Last resort: return last known price (stale but safe)
        # BTC Sanity: all sources failed — fall back silently to last known price
        return last_known if last_known > 0 else 0

    def fetch_oracle_price(self):
        if self.chainlink_contract:
            try:
                price = self.chainlink_contract.functions.latestAnswer().call()
                return float(price) / 10**8
            except: pass
        return 0.0

    def reset_history(self):
        self.price_history = []

    def update_history(self, curr_price, start_ts, elapsed):
        if self.first_update and not self.price_history and elapsed > 5:
            self.first_update = False
            try:
                r = requests.get("https://api.kraken.com/0/public/OHLC", 
                                 params={"pair":"XBTUSD", "interval":1, "since":start_ts-60}, 
                                 timeout=2).json()
                
                if 'result' in r and 'XXBTZUSD' in r['result']:
                    candles = r['result']['XXBTZUSD']
                    target_candle = next((c for c in candles if int(c[0]) == start_ts), None)
                    
                    if target_candle:
                        open_p = float(target_candle[1]) 
                        self.price_history.append({'timestamp': start_ts, 'elapsed': 0, 'price': open_p})
                        self.log(f"[cyan]Fixed Mid-Window Start: Found Kraken Open @ ${open_p:,.2f}[/]")
            except:
                pass
        
        self.first_update = False
        self.price_history.append({'timestamp': time.time(), 'elapsed': elapsed, 'price': curr_price})
        return self.price_history[0]['price'] if self.price_history else curr_price

    def fetch_polymarket(self, slug):
        up_id, down_id = None, None
        up_bid, down_bid = 0.5, 0.5
        up_ask, down_ask = 0.51, 0.51
        try:
            m = requests.get(f"https://gamma-api.polymarket.com/markets/slug/{slug}", timeout=2).json()
            ids = json.loads(m["clobTokenIds"]); outs = json.loads(m["outcomes"])
            
            is_up_first = any(x in outs[0].lower() for x in ["up", "yes", "above", "higher", "top"])
            if is_up_first:
                up_id, down_id = ids[0], ids[1]
            else:
                is_down_first = any(x in outs[0].lower() for x in ["down", "no", "below", "lower", "bottom"])
                if is_down_first:
                    down_id, up_id = ids[0], ids[1]
                else:
                    up_id = ids[0] if "Up" in outs[0] else ids[1]
                    down_id = ids[1] if up_id == ids[0] else ids[0]
            
            def get_p(tid, side):
                try: 
                    return float(requests.get("https://clob.polymarket.com/price", params={"token_id":tid,"side":side}, timeout=1).json().get("price",0))
                except: return 0
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                f_ub = executor.submit(get_p, up_id, "sell")
                f_db = executor.submit(get_p, down_id, "sell")
                f_ua = executor.submit(get_p, up_id, "buy")
                f_da = executor.submit(get_p, down_id, "buy")
                
                up_bid = f_ub.result()
                down_bid = f_db.result()
                up_ask = f_ua.result()
                down_ask = f_da.result()
            
        except Exception:
            pass
        
        return {
            "up_price": up_bid or 0.5, 
            "down_price": down_bid or 0.5,
            "up_bid": up_bid, 
            "down_bid": down_bid,
            "up_ask": up_ask,
            "down_ask": down_ask,
            "up_id": up_id, 
            "down_id": down_id
        }
