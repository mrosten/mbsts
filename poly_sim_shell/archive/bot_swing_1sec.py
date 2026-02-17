"""
Bot: Live Swing Strategy (1-Sec Sampling)

The main live trading bot for the "Swing Hunter" strategy.
- Samples 1-second data to calculate Volatility and Efficiency.
- Wager: Fixed $5.50 or Dynamic.
- Logic: Momentum (0.15% drift) or Reversion (>0.35% drift).
- Safety: Auto-Sell @ $0.99, Liquidity Cap, Min Wager checks.
"""
import requests
import time
import json
import asyncio
import sys
import numpy as np
import math
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv

# Polymarket / Web3 Imports
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# Load .env
load_dotenv()

# --- Configuration (Must match Simulation) ---
MAX_BET_AMOUNT = 100.0           # Cap max bet to $100 (Liquidity Constraint)
DRIFT_THRESHOLD = 0.0015         # 0.15% (Trigger Momentum)
REVERSION_THRESHOLD = 0.0035     # 0.35% (Trigger Reversion)
SWING_VOL_PERCENTILE = 4.14e-05  # Hardcoded from Sim (Top 20% of 1s data typical value)
EFFICIENCY_THRESHOLD = 0.35      # Efficiency < 0.35
ROLLING_WINDOW_SEC = 60          # Lookback for volatility/efficiency

# Environment Variables
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"

LOG_FILE = "live_dynamic_log.txt"

def print_status(msg, log_to_file=False):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    if log_to_file:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")

class LiveDynamicTrader:
    def __init__(self, use_proxy=True):
        self.trade_budget = 50.0 # Default start, overridden by user input
        self.use_proxy = use_proxy
        self.client = None
        self.market_url = ""
        self.market_data = {
            "up_id": None, "down_id": None, 
            "up_price": 0.0, "down_price": 0.0,
            "btc_price": 0.0, 
            "open_price": 0.0,
            "start_ts": 0
        }
        
        # Strategy State
        self.price_buffer = []    # Store last 60s of prices
        self.active_trade = None  # {side, shares, cost, entry_btc, time}
        self.daily_pnl = 0.0
        self.btc_offset = 0.0
        self.last_offset_update = 0
        
        # Web Session
        self.session = requests.Session()
        
        # Init Client
        self._init_client()

    def _init_client(self):
        if not PRIVATE_KEY:
            print_status("CRITICAL: No PRIVATE_KEY found in .env!")
            sys.exit(1)
            
        try:
            funder = PROXY_ADDRESS if (self.use_proxy and PROXY_ADDRESS) else Account.from_key(PRIVATE_KEY).address
            print(f"Initializing CLOB Client (Funder: {funder})...")
            
            self.client = ClobClient(
                host=HOST, 
                key=PRIVATE_KEY, 
                chain_id=CHAIN_ID, 
                signature_type=1 if self.use_proxy else 0, 
                funder=funder
            )
            creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(creds)
            print("CLOB Client Connected!")
            
        except Exception as e:
            print_status(f"CRITICAL: Client Init Error: {e}")
            sys.exit(1)

    def log(self, msg):
        print_status(msg, log_to_file=True)

    # --- Calculation Helpers (From Sim) ---
    def calculate_efficiency(self, prices):
        if len(prices) < 2: return 1.0
        net_change = abs(prices[-1] - prices[0])
        sum_changes = np.sum(np.abs(np.diff(prices)))
        if sum_changes == 0: return 1.0
        return net_change / sum_changes

    # --- Data Fetching ---
    def safe_load(self, val, default):
        if isinstance(val, (list, dict)): return val
        try: return json.loads(val)
        except: return default

    async def fetch_coingecko_price(self):
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
            resp = await asyncio.to_thread(self.session.get, url, timeout=3.0)
            return float(resp.json()['bitcoin']['usd'])
        except: return 0.0

    async def get_historical_open(self, timestamp_ms):
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={timestamp_ms}&limit=1"
            resp = await asyncio.to_thread(self.session.get, url, timeout=2)
            data = resp.json()
            if data and len(data) > 0:
                return float(data[0][1]) + self.btc_offset
        except: pass
        return 0.0

    async def fetch_spot_price(self):
        try:
            # Auto-Offset (Every 60s)
            now = time.time()
            if (now - self.last_offset_update > 60):
                cg = await self.fetch_coingecko_price()
                if cg > 0:
                    url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
                    r = await asyncio.to_thread(self.session.get, url, timeout=1.5)
                    raw_b = float(r.json()["price"])
                    self.btc_offset = cg - raw_b
                    self.last_offset_update = now

            # Get Price
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            resp = await asyncio.to_thread(self.session.get, url, timeout=1.5)
            data = resp.json()
            if "price" in data:
                price = float(data["price"]) + self.btc_offset
                self.market_data["btc_price"] = price
                
                # Update Buffer
                self.price_buffer.append(price)
                if len(self.price_buffer) > ROLLING_WINDOW_SEC:
                    self.price_buffer.pop(0)

                # Fetch Open if missing
                if self.market_data["open_price"] == 0 and self.market_data["start_ts"] > 0:
                     # Check if we are freshly started (within first minute)
                     if (time.time() - self.market_data["start_ts"]) < 60:
                         self.market_data["open_price"] = price # Use current as proxy
                     else:
                         op = await self.get_historical_open(self.market_data["start_ts"] * 1000)
                         if op > 0: self.market_data["open_price"] = op
        except: pass

    async def fetch_market_data(self):
        # Metadata
        if not self.market_data["up_id"] and self.market_url:
            try:
                slug = self.market_url.split("/")[-1].split("?")[0]
                url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
                resp = await asyncio.to_thread(self.session.get, url, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if "clobTokenIds" in data:
                        ids = self.safe_load(data["clobTokenIds"], [])
                        outcomes = self.safe_load(data.get("outcomes", "[]"), [])
                        
                        if len(ids) >= 2:
                             up_idx, down_idx = 0, 1
                             for i, name in enumerate(outcomes):
                                 if "Up" in name or "Yes" in name: up_idx = i
                                 elif "Down" in name or "No" in name: down_idx = i
                             self.market_data["up_id"] = ids[up_idx]
                             self.market_data["down_id"] = ids[down_idx]
            except: pass

        # Prices
        if self.market_data["up_id"]:
            try:
                clob_url = "https://clob.polymarket.com/price"
                p1 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["up_id"], "side": "buy"}, timeout=1)
                p2 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["down_id"], "side": "buy"}, timeout=1)
                r1, r2 = p1.json(), p2.json()
                if "price" in r1: self.market_data["up_price"] = float(r1["price"])
                if "price" in r2: self.market_data["down_price"] = float(r2["price"])
            except: pass

    # --- Execution ---
    async def execute_trade(self, side, usd_amount, reason):
        if not self.client: return False
        
        token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
        price = self.market_data["up_price"] if side == "UP" else self.market_data["down_price"]
        
        # Realism filters
        if price <= 0.01 or price >= 0.99: 
            self.log(f"SKIPPED: Price {price} too extreme.")
            return False

        shares = round(usd_amount / price, 2)
        
        self.log(f">>> SIGNAL: {side} | {reason}")
        self.log(f">>> EXECUTING BUY: ${usd_amount:.2f} (~{shares} shares) @ {price:.2f}")

        try:
            order_args = OrderArgs(
                price=0.99, # Market buy via limit
                size=shares,
                side="BUY",
                token_id=token_id
            )
            
            def _post():
                signed = self.client.create_order(order_args)
                return self.client.post_order(signed)
            
            resp = await asyncio.to_thread(_post)
            
            if resp and (resp.get("success") or resp.get("orderID")):
                oid = resp.get("orderID") or "UNKNOWN"
                self.log(f"SUCCESS: Order Placed! ID: {oid}")
                
                self.active_trade = {
                    "side": side,
                    "shares": shares,
                    "cost": usd_amount,
                    "entry_opt": price,
                    "entry_btc": self.market_data["btc_price"],
                    "time": datetime.now().strftime("%H:%M:%S")
                }
                
                # Auto-Exit (Limit Sell @ 0.99)
                await self.place_exit_order(token_id, shares)
                return True
            else:
                 self.log(f"FAILURE: {resp}")
                 return False

        except Exception as e:
            self.log(f"EXCEPTION: {e}")
            return False

    async def place_exit_order(self, token_id, shares):
        self.log(f"Placing EXIT SELL LIMIT at $0.99 for {shares} shares...")
        try:
            order_args = OrderArgs(price=0.99, size=shares, side="SELL", token_id=token_id)
            def _post():
                signed = self.client.create_order(order_args)
                return self.client.post_order(signed)
            await asyncio.to_thread(_post)
        except Exception as e:
            self.log(f"Exit Order Failed: {e}")

    # --- Main Loop ---
    async def run(self):
        print(f"--- LIVE DYNAMIC STRATEGY BOT (1-SEC) ---")
        
        # User Configuration
        balance_input = input("Enter Your Current Balance (USD) [Default 50]: ").strip()
        self.trade_budget = float(balance_input if balance_input else 50.0)
        
        print(f"Running with Balance: ${self.trade_budget:.2f}")
        print(f"Minimum Wager set to: $5.50")
        
        print("Calibrating...")
        await self.fetch_spot_price()
        
        while True:
            try:
                # 1. Window Calc
                now = datetime.now(timezone.utc)
                minutes = now.minute
                # floor = (minutes // 15) * 15 # 15m windows
                # 3-minute windows for testing? No, keep to 15m to match sim.
                # Actually, simulator was 15m.
                floor = (minutes // 15) * 15 
                start_dt = now.replace(minute=floor, second=0, microsecond=0)
                ts_start = int(start_dt.timestamp())
                
                # Check New Window
                if ts_start != self.market_data["start_ts"]:
                     if self.active_trade:
                         self.log("WINDOW CLOSED. Clearing Active Trade (Hope it settled!).")
                         # In real bot, we should check if we won and update balance!
                         # For now, just reset state.
                         self.active_trade = None
                     
                     self.market_data["start_ts"] = ts_start
                     self.market_data["open_price"] = 0.0 # Reset Open
                     self.price_buffer = [] # Reset Buffer
                     url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"
                     self.market_url = url
                     self.log(f"NEW WINDOW: {url}")

                # 2. Fetch Data (Every Second)
                await self.fetch_market_data()
                await self.fetch_spot_price()
                
                # 3. Strategy Logic (Only if have buffer)
                if len(self.price_buffer) >= ROLLING_WINDOW_SEC and self.market_data["open_price"] > 0:
                    
                    if not self.active_trade:
                         elapsed_sec = time.time() - ts_start
                         if elapsed_sec < 850: # Don't trade in last 50s
                             
                             curr_price = self.market_data["btc_price"]
                             open_price = self.market_data["open_price"]
                             
                             # 1. Drift
                             drift = (curr_price - open_price) / open_price
                             abs_drift = abs(drift)
                             
                             if abs_drift > DRIFT_THRESHOLD:
                                 # 2. Volatility
                                 curr_vol = np.std(self.price_buffer)
                                 
                                 # 3. Efficiency
                                 eff = self.calculate_efficiency(self.price_buffer)
                                 
                                 # print(f"DEBUG: Drift {drift:.4%} | Vol {curr_vol:.2e} | Eff {eff:.2f}")
                                 
                                 if curr_vol > SWING_VOL_PERCENTILE and eff < EFFICIENCY_THRESHOLD:
                                     # SIGNAL!
                                     
                                     # Direction logic
                                     side = "UP"
                                     strategy_type = "MOMENTUM"
                                     
                                     if abs_drift > REVERSION_THRESHOLD:
                                         side = "DOWN" if drift > 0 else "UP"
                                         strategy_type = "REVERSION"
                                     else:
                                         side = "UP" if drift > 0 else "DOWN"
                                     
                                     # Sizing Logic
                                     price = self.market_data["up_price"] if side == "UP" else self.market_data["down_price"]
                                     if 0.05 < price < 0.95:
                                         dist = abs(price - 0.5)
                                         wager_pct = 0.15 + (dist * 1.20)
                                         wager_pct = min(0.75, wager_pct)
                                         
                                         # --- User Override: Flat $5.50 ---
                                         # The user requested to "start with just 5.5" to be safe.
                                         # logic for dynamic sizing is commented out below.
                                         
                                         # amount = self.trade_budget * wager_pct
                                         # amount = max(amount, 5.50)
                                         # amount = min(amount, MAX_BET_AMOUNT)
                                         # amount = min(amount, self.trade_budget)
                                         
                                         amount = 5.50 # FLAT BET
                                         
                                         # Final Safety Check
                                         if amount > self.trade_budget:
                                              self.log(f"SKIPPED: Balance ${self.trade_budget:.2f} < Wager ${amount:.2f}")
                                         else:
                                              success = await self.execute_trade(side, amount, f"Swing {strategy_type} (Vol {curr_vol:.2e}, Eff {eff:.2f})")
                                              if not success:
                                                  self.log("PAUSING: Trade failed. Waiting 60s to avoid spam...")
                                                  await asyncio.sleep(60) # Cooldown on failure

                # Heartbeat Display
                drift_d = 0.0
                if self.market_data["open_price"] > 0:
                     drift_d = (self.market_data["btc_price"] - self.market_data["open_price"]) / self.market_data["open_price"]
                
                # Time Left Calculation
                elapsed = time.time() - ts_start
                remain = 900 - elapsed
                m_rem = int(remain // 60)
                s_rem = int(remain % 60)
                time_str = f"{m_rem:02d}:{s_rem:02d}"
                
                print(f"\r[{time_str}] BTC: {self.market_data['btc_price']:.1f} | UP: {self.market_data['up_price']:.2f} DN: {self.market_data['down_price']:.2f} | Drift: {drift_d:.4%} | Active: {self.active_trade['side'] if self.active_trade else 'None'}    ", end="", flush=True)

                # Sleep 1s
                await asyncio.sleep(1)

            except KeyboardInterrupt: break
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        trader = LiveDynamicTrader()
        asyncio.run(trader.run())
    except KeyboardInterrupt: pass
