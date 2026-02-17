import time
import requests
import json
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
        
    def log(self, msg):
        self.logger(msg)

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
            # Returns: Close prices, Low prices, High prices, and the full OHLC for index matching
            return [float(x[4]) for x in data], [float(x[3]) for x in data], [float(x[2]) for x in data], data
        except Exception as e:
            self.log(f"[yellow]Warn: candles Fetch Failed: {e}[/]")
            return [], [], [], []

    def fetch_current_price(self):
        # 1. Try Kraken (Closest to Polymarket Match)
        try:
            r = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD", timeout=1).json()
            return float(r['result']['XXBTZUSD']['c'][0])
        except: pass

        # 2. Try Chainlink (Oracle Price)
        if self.chainlink_contract:
            try:
                price = self.chainlink_contract.functions.latestAnswer().call()
                return float(price) / 10**8 # BTC/USD on Chainlink has 8 decimals
            except: pass

        # 3. Fallback to Binance (Real-time Exchange Price)
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=2).json()
            return float(r['price'])
        except Exception: 
            return self.market_data["btc_price"] 

    def fetch_oracle_price(self):
        """Specifically fetches the Chainlink Oracle price for drift check."""
        if self.chainlink_contract:
            try:
                price = self.chainlink_contract.functions.latestAnswer().call()
                return float(price) / 10**8
            except: pass
        return 0.0

    def reset_history(self):
        self.price_history = []

    def update_history(self, curr_price, start_ts, elapsed):
        # If we just started mid-window and have no history, try to find the actual open price
        if self.first_update and not self.price_history and elapsed > 5:
            self.first_update = False
            try:
                # Fetch Kraken OHLC (1-min intervals) to find the open
                # Kraken returns [time, open, high, low, close, vwap, vol, count]
                # We need "since" parameter roughly around start_ts
                r = requests.get("https://api.kraken.com/0/public/OHLC", 
                                 params={"pair":"XBTUSD", "interval":1, "since":start_ts-60}, 
                                 timeout=2).json()
                
                # Find the candle that matches our start_ts exactly
                if 'result' in r and 'XXBTZUSD' in r['result']:
                    candles = r['result']['XXBTZUSD']
                    target_candle = next((c for c in candles if int(c[0]) == start_ts), None)
                    
                    if target_candle:
                        open_p = float(target_candle[1]) # Index 1 is Open
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
            
            up_bid = get_p(up_id, "sell")
            down_bid = get_p(down_id, "sell")
            up_ask = get_p(up_id, "buy")
            down_ask = get_p(down_id, "buy")
            
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
