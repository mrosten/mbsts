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

def calculate_atr(highs, lows, closes, period=14):
    if len(highs) < period + 1: return 0
    tr_list = []
    for i in range(1, len(highs)):
        h, l, pc = highs[i], lows[i], closes[i-1]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_list.append(tr)
    # Simple Moving Average of TR
    return sum(tr_list[-period:]) / period

class MarketDataManager:
    def __init__(self, logger_func=None):
        self.logger = logger_func if logger_func else print
        self.market_data = {
            "btc_price": 0, "btc_open": 0, "start_ts": 0, 
            "up_p": 0.5, "down_p": 0.5, "up_price": 0.5, "down_price": 0.5,
            "up_bid": 0.5, "down_bid": 0.5, "up_ask": 0.51, "down_ask": 0.51,
            "up_id": None, "down_id": None,
            "sling_signal": "OFF", "cobra_signal": "OFF", "flag_signal": "OFF",
            "master_score": 0, "master_status": "NEUTRAL", "active_scanners": 0,
            "trend_4h": "NEUTRAL", "trend_1h": "NEUTRAL",
            "rsi_1m": 50.0, "atr_5m": 0.0, "odds_score": 0, "btc_dyn_rng": 0,
            "vol_up": 0, "vol_dn": 0
        }
        self.chainlink_contract = None
        self.price_history = []
        self.trend_4h = "NEUTRAL"
        self.trend_1h = "NEUTRAL"  # Add 1-hour trend
        self.atr_5m = 0.0
        self.last_4h_update = 0
        self.last_1h_update = 0  # Add 1h update timer
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
            
            # Calculate trend strength percentage
            trend_pct = ((short / long_) - 1) * 100
            
            # Determine trend direction and strength
            if trend_pct >= 0.5:  # Strong uptrend (0.5%+)
                self.trend_4h = "S-UP"  # Strong UP
            elif trend_pct >= 0.2:  # Medium uptrend (0.2%+)
                self.trend_4h = "M-UP"  # Medium UP
            elif trend_pct >= 0.05:  # Weak uptrend (0.05%+)
                self.trend_4h = "W-UP"  # Weak UP
            elif trend_pct <= -0.5:  # Strong downtrend (-0.5%+)
                self.trend_4h = "S-DOWN"  # Strong DOWN
            elif trend_pct <= -0.2:  # Medium downtrend (-0.2%+)
                self.trend_4h = "M-DOWN"  # Medium DOWN
            elif trend_pct <= -0.05:  # Weak downtrend (-0.05%+)
                self.trend_4h = "W-DOWN"  # Weak DOWN
            else:
                self.trend_4h = "NEUTRAL"
                
            self.last_4h_update = time.time()
        except requests.RequestException as e:
            self.log(f"[yellow]Warn: 4H Trend Update Failed: {e}[/]")
        except Exception as e:
            self.log(f"[red]Error: 4H Trend Calc Error: {e}[/]")

    def update_1h_trend(self):
        """Calculate 1-hour trend for more responsive 5-minute market analysis."""
        if (time.time() - getattr(self, 'last_1h_update', 0)) < 900: return
        try:
            r = requests.get("https://api.binance.com/api/v3/klines", params={"symbol":"BTCUSDT","interval":"1h","limit":12}, timeout=3)
            r.raise_for_status()
            data = r.json()
            closes = [float(x[4]) for x in data]
            short = sum(closes[-3:]) / 3; long_ = sum(closes) / len(closes)
            
            # Calculate trend strength percentage
            trend_pct = ((short / long_) - 1) * 100
            
            # Determine trend direction and strength
            if trend_pct >= 0.3:  # Strong uptrend (0.3%+)
                self.trend_1h = "S-UP"  # Strong UP
            elif trend_pct >= 0.15:  # Medium uptrend (0.15%+)
                self.trend_1h = "M-UP"  # Medium UP
            elif trend_pct >= 0.05:  # Weak uptrend (0.05%+)
                self.trend_1h = "W-UP"  # Weak UP
            elif trend_pct <= -0.3:  # Strong downtrend (-0.3%+)
                self.trend_1h = "S-DOWN"  # Strong DOWN
            elif trend_pct <= -0.15:  # Medium downtrend (-0.15%+)
                self.trend_1h = "M-DOWN"  # Medium DOWN
            elif trend_pct <= -0.05:  # Weak downtrend (-0.05%+)
                self.trend_1h = "W-DOWN"  # Weak DOWN
            else:
                self.trend_1h = "NEUTRAL"
                
            self.last_1h_update = time.time()
        except requests.RequestException as e:
            self.log(f"[yellow]Warn: 1H Trend Update Failed: {e}[/]")
        except Exception as e:
            self.log(f"[red]Error: 1H Trend Calc Error: {e}[/]")

    def update_atr(self):
        """Fetches 1m klines and updates the 5-period ATR (Average True Range)."""
        try:
            closes, lows, highs, _ = self.fetch_candles_60m()
            if highs and lows and closes:
                self.atr_5m = calculate_atr(highs, lows, closes, period=5)
        except Exception as e:
            self.log(f"[yellow]Warn: ATR Update Failed: {e}[/]")

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
            ids = m["clobTokenIds"] if isinstance(m["clobTokenIds"], list) else json.loads(m["clobTokenIds"])
            outs = m["outcomes"] if isinstance(m["outcomes"], list) else json.loads(m["outcomes"])
            # self.log(f"[dim]Outcomes: {outs} | IDs: {[i[:6] for i in ids]}[/]")
            
            # Robust outcome check
            idx_up, idx_down = None, None
            for i, o in enumerate(outs):
                o_low = str(o).lower()
                if any(x in o_low for x in ["up", "yes", "above", "higher", "top"]):
                    idx_up = i
                elif any(x in o_low for x in ["down", "no", "below", "lower", "bottom"]):
                    idx_down = i
            
            if idx_up is not None and idx_down is not None:
                up_id, down_id = ids[idx_up], ids[idx_down]
            else:
                # Fallback to simple order if parsing fails
                up_id, down_id = ids[0], ids[1]
            
            def get_p(tid, side):
                try: 
                    return float(requests.get("https://clob.polymarket.com/price", params={"token_id":tid,"side":side}, timeout=1).json().get("price",0))
                except: return 0
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                # side="buy" is the price to BUY (Ask), side="sell" is the price to SELL (Bid)
                f_ua = executor.submit(get_p, up_id, "buy")
                f_da = executor.submit(get_p, down_id, "buy")
                f_ub = executor.submit(get_p, up_id, "sell")
                f_db = executor.submit(get_p, down_id, "sell")
                
                up_ask = f_ua.result()
                down_ask = f_da.result()
                up_bid = f_ub.result()
                down_bid = f_db.result()

            # Volume at Open: BTC liquidity near the 5-min window open price (throttled 5s)
            curr_t = time.time()
            if curr_t - getattr(self, "last_vol_update", 0) > 5:
                try:
                    b_depth = requests.get(
                        "https://api.binance.com/api/v3/depth",
                        params={"symbol": "BTCUSDT", "limit": 1000},
                        timeout=1.5
                    ).json()

                    open_p = self.market_data.get("btc_open", 0)

                    if open_p > 0:
                        # V-UP: bids AT or ABOVE open → buyers holding price green
                        self.market_data["vol_up"] = sum(
                            float(b[1]) for b in b_depth.get("bids", [])
                            if float(b[0]) >= open_p
                        )
                        # V-DN: asks AT or BELOW open → sellers keeping price red
                        self.market_data["vol_dn"] = sum(
                            float(a[1]) for a in b_depth.get("asks", [])
                            if float(a[0]) <= open_p
                        )
                    else:
                        # Fallback: no open price yet, show whole book totals
                        self.market_data["vol_up"] = sum(float(b[1]) for b in b_depth.get("bids", []))
                        self.market_data["vol_dn"] = sum(float(a[1]) for a in b_depth.get("asks", []))

                    self.last_vol_update = curr_t
                except Exception as e:
                    self.log(f"[yellow]Binance Vol Error: {e}[/]")

            vol_up = self.market_data.get("vol_up", 0)
            vol_dn = self.market_data.get("vol_dn", 0)
            
        except Exception as e:
            self.log(f"[red]Polymarket Fetch Error ({slug}): {e}[/]")
        
        # Best Estimate of 'Current Price' is Midpoint or Bid/Ask
        def _best(b, a):
            if b > 0 and a > 0: return (b+a)/2
            return a or b or 0.5

        return {
            "up_price": _best(up_bid, up_ask), 
            "down_price": _best(down_bid, down_ask),
            "up_bid": up_bid, 
            "down_bid": down_bid,
            "up_ask": up_ask,
            "down_ask": down_ask,
            "up_id": up_id, 
            "down_id": down_id,
            "vol_up": vol_up,
            "vol_dn": vol_dn
        }
