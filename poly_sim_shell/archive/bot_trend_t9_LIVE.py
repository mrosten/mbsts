"""
Bot: Legacy Trend Strategy (T+9)

The classic "Early Bird / Hybrid" strategy bot.
- Checks Drift > 0.04% at T+6 and T+9 minutes.
- Features Manual Confirmation mode (Press 'Yes') and Auto-Sell @ $0.99.
- Simple drift-following logic without volatility filters.
"""
import requests
import time
import json
import asyncio
import sys
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv

# Polymarket / Web3 Imports
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# Load .env from current directory (poly_sim_shell)
load_dotenv()

STATE_FILE = "live_trade_state.json"
LOG_FILE = "live_trade_log.txt"

# Environment Variables
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"

# --- CLI Helpers ---
def print_status(msg, log_to_file=False):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    if log_to_file:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")

# --- Core Logic ---
class LiveTrader:
    def __init__(self, use_proxy=True):
        self.trade_size = 5.5 # DOLLARS (Not shares, we calc shares)
        # Note: In real API, size is SHARES. We will calc (USD / Price) -> Shares.
        
        # Offsets
        self.OFFSET_JERUSALEM = timedelta(hours=2)
        self.btc_offset = -86.0
        self.auto_offset = True
        self.last_offset_update = 0
        self.last_trade_ts = 0 # FAILSAFE for double execution
        
        # State
        self.active_trade = None # {"token_id": "0x...", "side": "UP", "shares": 10.0, "cost": 5.50}
        self.is_running = True
        self.market_url = ""
        self.market_data = {
            "up_id": None, "down_id": None, 
            "up_price": 0.0, "down_price": 0.0,
            "btc_price": 0.0, 
            "open_price": 0.0,
            "start_ts": 0, "end_ts": 0
        }
        self.strategy_triggered = False
        self.session = requests.Session()
        
        # CLOB Client
        self.client = None
        self.use_proxy = use_proxy
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
                signature_type=1 if self.use_proxy else 0, # 1 for Proxy, 0 for EOA
                funder=funder
            )
            # Derive API Creds (L2)
            creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(creds)
            print("CLOB Client Connected!")
            
        except Exception as e:
            print_status(f"CRITICAL: Client Init Error: {e}")
            sys.exit(1)

    def log(self, msg):
        print_status(msg, log_to_file=True)

    # --- Data Fetching (Exact copy from sim_cli) ---
    def safe_load(self, val, default):
        if isinstance(val, (list, dict)): return val
        try: return json.loads(val)
        except: return default

    async def fetch_coingecko_price(self):
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
            resp = await asyncio.to_thread(self.session.get, url, timeout=3.0)
            data = resp.json()
            return float(data['bitcoin']['usd'])
        except: return 0.0

    async def get_historical_open(self, timestamp_ms):
        ts_str = datetime.fromtimestamp(timestamp_ms/1000, tz=timezone.utc).strftime('%H:%M:%S')
        self.log(f"DEBUG: Querying Historical Open for {ts_str} (TS: {timestamp_ms})...")
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
            # Auto-Offset
            now = time.time()
            if self.auto_offset and (now - self.last_offset_update > 60):
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
                
                # Check Open
                if self.market_data["open_price"] == 0 and self.market_data["start_ts"] > 0:
                     op = await self.get_historical_open(self.market_data["start_ts"] * 1000)
                     if op > 0: 
                         self.market_data["open_price"] = op
                         self.log(f"OPEN PRICE CACHED: {op}")
                     elif (time.time() - self.market_data["start_ts"]) < 60:
                         self.market_data["open_price"] = price
                         self.log(f"OPEN PRICE SET (LIVE): {price} (Used Current Price as window just started)")
                     else:
                         self.log(f"DEBUG: Still missing Open Price. Retry next loop...")
                         pass # Retry next loop
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
                        
                        # Robust Mapping
                        if len(ids) >= 2 and len(outcomes) >= 2:
                             # Default
                             up_idx, down_idx = 0, 1
                             
                             # Try to find by name
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

    # --- Trading Logic (REAL) ---
    async def execute_market_buy(self, side, token_id, usd_amount):
        if not self.client: return False
        
        # FAILSAFE: Prevent double execution within 60 seconds
        if time.time() - self.last_trade_ts < 60:
            self.log("WARNING: Trade blocked by 60s cooldown (Double Execution Protection).")
            return None
        
        # Get approx price to calculate shares
        price = self.market_data["up_price"] if side == "UP" else self.market_data["down_price"]
        if price <= 0: price = 0.50 # Safety fallback
        
        # Cap price at 0.99 to execute immediately
        limit_price = 0.99
        
        # SANITY CHECK: Never buy below $0.40 (Likely wrong side or crash)
        if price < 0.40:
             self.log(f"WARNING: Price {price:.2f} is too low! Aborting trade (Safety Check).")
             return None
             
        # Shares = USD / Price (This is an approximation)
        # Better: Shares = USD / Limit Price? No, that underestimates.
        # Shares = USD / Current Price.
        shares = float(usd_amount) / price
        shares = round(shares, 2)
        
        self.log(f"Initiating BUY {side}: ${usd_amount} (~{shares} Shares) on Token {token_id}...")
        
        try:
            # Create Order
            order_args = OrderArgs(
                price=limit_price,
                size=shares,
                side="BUY",
                token_id=token_id
            )
            
            # Sign & Post
            # Sync call in thread
            def _post():
                signed = self.client.create_order(order_args)
                return self.client.post_order(signed)
            
            resp = await asyncio.to_thread(_post)
            print(f"API Response: {resp}")
            
            if resp and (resp.get("success") or resp.get("orderID")):
                oid = resp.get("orderID") or "UNKNOWN"
                self.log(f"SUCCESS: Order Placed! ID: {oid}")
                self.last_trade_ts = time.time()
                return {
                    "side": side,
                    "shares": shares,
                    "cost": usd_amount, # Approximate
                    "order_id": oid,
                    "token_id": token_id
                }
            else:
                 err = resp.get("errorMsg") if resp else "Unknown"
                 self.log(f"FAILURE: Order Failed: {err}")
                 return None
                 
        except Exception as e:
            self.log(f"EXCEPTION: Trade Error: {e}")
            return None

    # --- Exit Strategy ---
    async def place_exit_order(self, token_id, shares):
        if not self.client: return
        
        self.log(f"Placing EXIT SELL LIMIT at $0.99 for {shares} shares...")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Create Sell Order
                order_args = OrderArgs(
                    price=0.99,
                    size=shares,
                    side="SELL",
                    token_id=token_id
                )
                
                # Sign & Post
                def _post():
                    signed = self.client.create_order(order_args)
                    return self.client.post_order(signed)
                
                resp = await asyncio.to_thread(_post)
                
                if resp and (resp.get("success") or resp.get("orderID")):
                    oid = resp.get("orderID") or "UNKNOWN"
                    self.log(f"SUCCESS: Exit Order Placed! ID: {oid}")
                    return # Done
                else:
                    err = resp.get("errorMsg") if resp else "Unknown"
                    self.log(f"Retry {attempt+1}/{max_retries}: Exit Order Failed ({err}). Waiting for balance update...")
            
            except Exception as e:
                self.log(f"Retry {attempt+1}/{max_retries}: Error {e}")
            
            # Backoff wait (1s, 2s, 3s)
            await asyncio.sleep(attempt + 1.5)
        
        self.log("FAILURE: Could not place Exit Order after 3 attempts.")

    # --- Main Loop ---
    async def run(self):
        print(f"--- LIVE TRADING BOT (REAL MONEY) ---")
        
        # --- Startup Config ---
        print("\n--- CONFIGURATION ---")
        # 1. Ask about Confirmation
        print("1. Do you want to be asked to confirm trades? (Manual Mode)")
        ans_confirm = input("   (y/n, default=y): ").strip().lower()
        self.manual_confirm = (ans_confirm != 'n')
        if not self.manual_confirm:
            print("   >>> WARNING: AUTO-EXECUTION ENABLED. TRADES WILL FIRE IMMEDIATELY! <<<")
        else:
            print("   >>> SAFETY: Manual Confirmation Enabled using 'YES'.")
            
        # 2. Ask about T+6
        print("2. Do you want to enable the 6-minute trade option?")
        ans_t6 = input("   (y/n, default=y): ").strip().lower()
        self.enable_t6 = (ans_t6 != 'n')
        print(f"   >>> T+6 Option: {'ENABLED' if self.enable_t6 else 'DISABLED'}")
        print("---------------------\n")
        
        print(f"Trade Size: ${self.trade_size}")
        print("Calibrating Price Offset...")
        await self.fetch_spot_price()
        print(f"Offset: {self.btc_offset:.2f}")
        if self.market_url:
            self.log(f"Resumed Monitoring: {self.market_url}")

        while self.is_running:
            try:
                # 1. Sync Price (Moved after Window Calc)
                # await self.fetch_spot_price()

                # 2. Window Calc
                now = datetime.now(timezone.utc)
                minutes = now.minute
                floor = (minutes // 15) * 15
                start_dt = now.replace(minute=floor, second=0, microsecond=0)
                end_dt = start_dt + timedelta(minutes=15)
                ts_start = int(start_dt.timestamp())
                url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"
                
                # Check New Market (Reset)
                if url != self.market_url:
                    if self.market_url != "":
                         self.log("MARKET CLOSED / NEW WINDOW")
                         # Here we assume auto-payout handling by Poly (we don't need to sell to close expiries)
                         
                    self.market_url = url
                    self.log(f"Monitoring: {self.market_url}") # Log the URL
                    btc = self.market_data["btc_price"]
                    self.market_data = {
                        "up_id": None, "down_id": None, 
                        "up_price": 0.0, "down_price": 0.0,
                        "btc_price": btc, 
                        "open_price": 0.0,
                        "start_ts": ts_start, "end_ts": end_dt.timestamp()
                    }
                    self.strategy_triggered = False
                    self.active_trade = None 
                    
                # 3. Fetch Data
                await self.fetch_market_data()
                await self.fetch_spot_price() # Sync Price & Open (Correctly sequenced after Window Calc)
                
                # 4. Strategy Execution Logic (Moved BEFORE Plan)
                drift_pct = 0.0
                if self.market_data["open_price"] > 0:
                     drift_pct = abs(self.market_data["btc_price"] - self.market_data["open_price"]) / self.market_data["open_price"]
                
                # Calc elapsed first for checks
                elapsed_mins = (time.time() - ts_start) / 60.0
                
                check_t6 = 5.9 <= elapsed_mins <= 6.1
                check_t9 = 8.9 <= elapsed_mins <= 9.1
                
                # LOGIC: Check T+9 OR (T+6 AND Enabled)
                is_window = check_t9 or (check_t6 and self.enable_t6)
                
                if is_window and not self.strategy_triggered and not self.active_trade:
                    if drift_pct > 0.0004:
                         side = "UP" if self.market_data["btc_price"] > self.market_data["open_price"] else "DOWN"
                         token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
                         price = self.market_data["up_price"] if side == "UP" else self.market_data["down_price"]
                         
                         if token_id and price > 0:
                             # REALITY CHECK
                             if price < 0.30:
                                 self.log(f"INVALID SIGNAL: {side} indicated mathematically (Drift > 0.04%), but Market Price {price:.2f} confirms logic error/miscalibration. FORCING RE-CALIBRATION...")
                                 self.btc_offset = 0.0 # Force reset next loop
                                 self.last_offset_update = 0
                                 self.strategy_triggered = True
                                 await self.fetch_spot_price() # Immediate resync
                                 continue
                             
                             if price < 0.55:
                                 self.log(f"SKIPPED: {side} signal valid, but Price {price:.2f} too low/risky.")
                                 self.strategy_triggered = True
                                 continue

                             self.log(f"SIGNAL: {side} @ {price:.2f} (Drift {drift_pct:.4%})")
                             
                             # EXECUTION BLOCK
                             should_execute = False
                             
                             if self.manual_confirm:
                                 # MANUAL CONFIRMATION
                                 print(f"\n>>> CONFIRM PURCHASE: {side} @ {price:.2f} (${self.trade_size})?")
                                 print(">>> TYPE 'YES' TO EXECUTE (Anything else to Cancel)")
                                 # Bell sound (ASCII 7) to alert user
                                 print('\a') 
                                 # Use separate thread/timeout for input if needed? 
                                 # For simplicity in CLI, blocking input is okay as window is 12s, but user must be fast.
                                 confirm = input(">>> ").strip().lower()
                                 if confirm == 'yes':
                                     should_execute = True
                                 else:
                                     self.log("Trade CANCELLED by user.")
                                     self.strategy_triggered = True # Skip rest of window
                             else:
                                 # AUTO MODE
                                 self.log("AUTO-EXECUTING Signal...")
                                 should_execute = True
                             
                             if should_execute:
                                 # OPTIMISTIC LOCK: Prevent double execution loop
                                 self.strategy_triggered = True
                                 
                                 # EXECUTE REAL TRADE
                                 res = await self.execute_market_buy(side, token_id, self.trade_size)
                                 
                                 if res:
                                     self.active_trade = res
                                     # AUTO-EXIT: Sell immediately at $0.99
                                     await self.place_exit_order(res["token_id"], res["shares"])
                    else:
                         print_status(f"No Signal: Drift {drift_pct:.4%} low.")
                         # Small sleep to avoid spamming log if we are in the 10s window
                         await asyncio.sleep(5) 

                # 5. Plan Determination
                
                # Checkpoints every 3 minutes (up to T+9)
                targets = [3.0, 6.0, 9.0, 15.0]
                next_target = 15.0
                mode = "NEXT BOUNDARY"
                
                # Find next target
                for t in targets:
                    if elapsed_mins < t:
                        next_target = t
                        if t == 6.0 or t == 9.0:
                            mode = f"CHECKPOINT (T+{int(t)}m)"
                        elif t == 15.0:
                            mode = "NEXT ROUND (Market Close)"
                        else:
                            mode = f"HEARTBEAT (T+{int(t)}m)"
                        break
                
                sleep_duration = (next_target * 60) - (elapsed_mins * 60)
                
                # Override if Strategy Done (in trade) -> Sleep to close
                if self.active_trade:
                    mode = "NEXT ROUND (Market Close)"
                    sleep_duration = (15.0 * 60) - (elapsed_mins * 60) 
                
                # Display
                trade_str = f"ACTIVE ({self.active_trade['side']})" if self.active_trade else "None"
                print_status(f"BTC: {self.market_data['btc_price']:,.1f} | OPEN: {self.market_data['open_price']:,.1f} | UP: {self.market_data['up_price']:.2f} DN: {self.market_data['down_price']:.2f} | Trade: {trade_str} | Drift: {drift_pct:.4%}")
                
                if sleep_duration > 5:
                    print(f"Waiting {int(sleep_duration)}s until {mode}...")
                    
                    # Smart Wait Loop (Updates every 30s)
                    remaining = sleep_duration
                    while remaining > 0:
                        step = min(30, remaining)
                        await asyncio.sleep(step)
                        remaining -= step
                        
                        if remaining > 0:
                            # Refresh Data during long waits
                            await self.fetch_spot_price()
                            await self.fetch_market_data()
                            
                            # Recalc Drift for Display
                            d_pct = 0.0
                            if self.market_data["open_price"] > 0:
                                d_pct = abs(self.market_data["btc_price"] - self.market_data["open_price"]) / self.market_data["open_price"]
                                
                            t_str = f"ACTIVE ({self.active_trade['side']})" if self.active_trade else "None"
                            print_status(f"[HEARTBEAT] BTC: {self.market_data['btc_price']:,.1f} | UP: {self.market_data['up_price']:.2f} DN: {self.market_data['down_price']:.2f} | Drift: {d_pct:.4%} | Remain: {int(remaining)}s")
                else:
                    await asyncio.sleep(5)

            except KeyboardInterrupt: break
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        trader = LiveTrader()
        asyncio.run(trader.run())
    except KeyboardInterrupt: pass
