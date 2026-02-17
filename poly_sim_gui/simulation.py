import requests
import time
import json
import numpy as np
import threading
import asyncio
from datetime import datetime, timezone, timedelta
from nicegui import ui, run

class SimulationStore:
    def __init__(self):
        self.balance = 50.0
        self.trade_size = 5.5
        
        # State
        self.active_trade = None
        self.trade_history = []
        self.is_running = False
        self.logs = []
        
        # Timezone Offsets
        self.OFFSET_JERUSALEM = timedelta(hours=2)
        self.OFFSET_ET = timedelta(hours=-5)
        
        # Market Data
        self.btc_offset = -86.0 
        self.auto_offset = True
        self.last_offset_update = 0
        self.market_url = ""
        self.market_data = {
            "up_id": None, "down_id": None, 
            "up_price": 0.0, "down_price": 0.0,
            "btc_price": 0.0, 
            "open_price": 0.0, # Formerly 'strike', now explicit 'Open'
            "end_ts": 0,
            "start_ts": 0
        }
        
        # Strategy Flags
        self.strategy_triggered_this_window = False
        
        # UI State
        self.ui_countdown = "--:--"
        self.ui_end_time = "--:--"
        
        self.session = requests.Session()

    def log(self, message):
        """Adds a log message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        self.logs.append(full_msg)
        # print(full_msg) # Keep console clean for CSV

    def start_simulation(self):
        self.is_running = True
        self.log("Simulation Started.")
        
    def stop_simulation(self):
        self.is_running = False
        self.log("Simulation Stopped.")

    def get_current_window_start(self):
        now = datetime.now(timezone.utc)
        minutes = now.minute
        floor_minutes = (minutes // 15) * 15
        start_dt = now.replace(minute=floor_minutes, second=0, microsecond=0)
        return start_dt

    # --- Historical Price Lookup (From market_analysis.py) ---
    def get_historical_open(self, timestamp_ms):
        # Try Binance First
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={timestamp_ms}&limit=1"
            resp = self.session.get(url, timeout=2)
            data = resp.json()
            if data and len(data) > 0:
                # Open price is index 1
                return float(data[0][1]) + self.btc_offset
        except:
            pass
            
        # Try CoinCap as fallback
        try:
            start = timestamp_ms
            end = start + 60000 
            url = f"https://api.coincap.io/v2/assets/bitcoin/history?interval=m1&start={start}&end={end}"
            resp = self.session.get(url, timeout=2)
            data = resp.json().get('data', [])
            if data:
                return float(data[0]['priceUsd']) + self.btc_offset
        except:
            pass
            
        return 0.0

    async def update_loop(self):
        """Main update loop."""
        # 1. Window Calculation
        now_utc = datetime.now(timezone.utc)
        start_dt = self.get_current_window_start()
        end_dt = start_dt + timedelta(minutes=15)
        
        ts_start = int(start_dt.timestamp())
        self.market_data["start_ts"] = ts_start
        self.market_data["end_ts"] = end_dt.timestamp()
        
        # Market URL
        current_expected_url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"
        if current_expected_url != self.market_url:
            self.market_url = current_expected_url
            # New Window -> Reset Data
            btc = self.market_data["btc_price"]
            self.market_data = {
                "up_id": None, "down_id": None, 
                "up_price": 0.0, "down_price": 0.0,
                "btc_price": btc, 
                "open_price": 0.0,
                "start_ts": ts_start,
                "end_ts": end_dt.timestamp()
            }
            self.strategy_triggered_this_window = False
            self.active_trade = None

        # Countdown
        remaining = end_dt - now_utc
        total_seconds = int(remaining.total_seconds())
        if total_seconds < 0:
            self.ui_countdown = "00:00"
        else:
            mins, secs = divmod(total_seconds, 60)
            self.ui_countdown = f"{mins:02}:{secs:02}"
            
        end_dt_jlm = end_dt + self.OFFSET_JERUSALEM
        self.ui_end_time = end_dt_jlm.strftime('%H:%M')

        # 2. Fetch Data
        await asyncio.gather(
            self.fetch_market_data(),
            self.fetch_spot_price(),
            return_exceptions=True
        )
        
        # 3. Process Strategy
        if self.is_running:
            self.process_strategy()
        
        # 4. Generate CSV
        self.generate_csv_log()

    async def fetch_spot_price(self):
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            resp = await run.io_bound(self.session.get, url, timeout=1.5)
            data = resp.json()
            if "price" in data:
                raw_binance = float(data["price"])
                
                # Auto-Offset Logic (Sync with CoinGecko every ~60s or if unset)
                # We use a primitive timer check
                now = time.time()
                if self.auto_offset and (now - self.last_offset_update > 60):
                     cg_price = await self.fetch_coingecko_price()
                     if cg_price > 0:
                         new_offset = cg_price - raw_binance
                         self.btc_offset = new_offset
                         self.last_offset_update = now
                         # self.log(f"Auto-Offset Updated: {new_offset:.2f} (CG: {cg_price})")

                # Store spot
                self.market_data["btc_price"] = raw_binance + self.btc_offset
                
                # Check Open (One-time fetch per window)
                if self.market_data["open_price"] == 0 and self.market_data["start_ts"] > 0:
                    # If we are IN the first minute, use current price as approximation if history fails
                    # But better to try fetch history
                     op = await run.io_bound(self.get_historical_open, self.market_data["start_ts"] * 1000)
                     if op > 0:
                         self.market_data["open_price"] = op
                     elif (time.time() - self.market_data["start_ts"]) < 60:
                         # Fallback: if we are very close to start, use current
                         self.market_data["open_price"] = self.market_data["btc_price"]
        except:
            pass

    async def fetch_coingecko_price(self):
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
            resp = await run.io_bound(self.session.get, url, timeout=3.0)
            data = resp.json()
            return float(data['bitcoin']['usd'])
        except:
            return 0.0

    async def fetch_market_data(self):
        if not self.market_data["up_id"]:
            # print("DEBUG: Missing Token IDs. Fetching Metadata...")
            await self.fetch_metadata()

        if self.market_data["up_id"]:
            try:
                # print(f"DEBUG: Fetching Prices for Tokens: {self.market_data['up_id']}, {self.market_data['down_id']}")
                clob_url = "https://clob.polymarket.com/price"
                def get_prices():
                    p1 = self.session.get(clob_url, params={"token_id": self.market_data["up_id"], "side": "buy"}, timeout=1.5).json()
                    p2 = self.session.get(clob_url, params={"token_id": self.market_data["down_id"], "side": "buy"}, timeout=1.5).json()
                    return p1, p2

                r1, r2 = await run.io_bound(get_prices)
                # print(f"DEBUG: CLOB Responses: {r1}, {r2}")
                
                if "price" in r1: self.market_data["up_price"] = float(r1["price"])
                if "price" in r2: self.market_data["down_price"] = float(r2["price"])
            except Exception as e:
                # print(f"DEBUG: CLOB Fetch Error: {e}")
                pass 
                
    def safe_load(self, val, default):
        if isinstance(val, (list, dict)): return val
        try:
            return json.loads(val)
        except:
            return default

    async def fetch_metadata(self):
        if not self.market_url: return
        try:
            slug = self.market_url.split("/")[-1]
            slug = slug.split("?")[0]
            
            gamma_url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
            # print(f"DEBUG: Fetching Metadata from {gamma_url}")
            
            resp = await run.io_bound(self.session.get, gamma_url, timeout=2.0)
            if resp.status_code != 200: 
                # print(f"DEBUG: Metadata Failed {resp.status_code}")
                return
            
            data = resp.json()
            print(f"DEBUG: Gamma Keys: {list(data.keys())}") 
            # Check for potential price fields
            # if 'start_price' in data: print(f"DEBUG: Start: {data['start_price']}")
            # if 'reference_price' in data: print(f"DEBUG: Ref: {data['reference_price']}")
            
            if "clobTokenIds" in data:
                 clob_ids = self.safe_load(data["clobTokenIds"], [])
                 if len(clob_ids) >= 2:
                     self.market_data["up_id"] = clob_ids[0]
                     self.market_data["down_id"] = clob_ids[1]
                     # print(f"DEBUG: Found Token IDs: {self.market_data['up_id']}, {self.market_data['down_id']}")
            else:
                 pass # print(f"DEBUG: No clobTokenIds in metadata: {data.keys()}")
        except Exception as e:
            # print(f"DEBUG: Metadata Exception: {e}")
            pass

    def process_strategy(self):
        if self.active_trade: return 
        if self.strategy_triggered_this_window: return
        if not self.market_data["open_price"]: return
        if not self.market_data["btc_price"]: return

        now_ts = time.time()
        elapsed_minutes = (now_ts - self.market_data["start_ts"]) / 60.0
        
        STRATEGY_THRESH = 0.0004 # 0.04%
        
        open_p = self.market_data["open_price"]
        current = self.market_data["btc_price"]
        
        # Signal Strength: Abs(Price - Open) / Open
        drift_pct = abs(current - open_p) / open_p
        
        # Logic: 
        # Check at 6m (5:45-6:15) OR 9m (8:45-9:15)
        # We use slightly wider windows to catch loop cycles
        is_t6 = 5.8 <= elapsed_minutes <= 6.2
        is_t9 = 8.8 <= elapsed_minutes <= 9.2
        
        signal_up = current > open_p
        
        if is_t6 or is_t9:
            if drift_pct > STRATEGY_THRESH:
                side = "UP" if signal_up else "DOWN"
                price = self.market_data["up_price"] if signal_up else self.market_data["down_price"]
                
                # Minimum price check (implied safety)
                if price >= 0.10: 
                    self.execute_trade(side, price)
                    self.strategy_triggered_this_window = True
                    self.log(f"Strategy Triggered at Minute {elapsed_minutes:.1f}: BUY {side} (Drift {drift_pct:.4f}%)")

    def execute_trade(self, side, price):
        if price <= 0: return
        cost = price * self.trade_size
        if cost > self.balance: return
            
        self.balance -= cost
        self.active_trade = {
            "side": side,
            "entry_price": price,
            "shares": self.trade_size,
            "ts": time.time(),
            "cost": cost
        }
        self.log(f"Entered: {side} @ {price:.3f}")

    def generate_csv_log(self):
        # CSV: Time, UP, DOWN, BTC, OPEN, DRIFT, SIGNAL
        time_str = self.ui_countdown
        
        up = self.market_data.get("up_price", 0)
        down = self.market_data.get("down_price", 0)
        btc = self.market_data.get("btc_price", 0)
        
        # Rename Strike -> Open for user clarity
        open_p = self.market_data.get("open_price", 0)
        
        drift = 0.0
        if open_p > 0:
            drift = abs(btc - open_p) / open_p
            
        sig = "WAIT"
        if self.active_trade: sig = f"IN-{self.active_trade['side']}"
        elif open_p > 0:
            # Show provisional signal
            direction = "UP" if btc > open_p else "DOWN"
            sig = f"LEAN-{direction}"
        
        # Log Format
        print(f"CSV: {time_str}, UP={up:.3f}, DOWN={down:.3f}, BTC={btc:.2f}, OPEN={open_p:.2f}, DRIFT={drift:.4%}, SIG={sig}")

simulation = SimulationStore()
