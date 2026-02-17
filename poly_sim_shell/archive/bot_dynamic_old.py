"""
Bot: (Deprecated) Dynamic Sizing V1

An earlier iteration of the active bot.
- Introduced the dynamic sizing logic (5% - 33%).
- Lacks the high-frequency 1-second interval checks of the current 'Swing' bot.
- Kept for reference.
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

STATE_FILE = "live_dynamic_state.json"
LOG_FILE = "live_dynamic_log.txt"

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
class LiveTraderDynamic:
    def __init__(self, use_proxy=True):
        self.risk_capital = 50.0 # Default, set in run()
        
        # Offsets
        self.OFFSET_JERUSALEM = timedelta(hours=2)
        self.btc_offset = -86.0
        self.auto_offset = True
        self.last_offset_update = 0
        self.last_trade_ts = 0 # FAILSAFE for double execution
        
        # Flags
        self.manual_confirm = True
        self.enable_t6 = True
        
        # State
        self.active_trade = None 
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
        self.seen_t3 = False
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

    # --- Data Fetching ---
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
                         self.log(f"OPEN PRICE SET (LIVE): {price}")
                     else:
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

    # --- Trading Logic (DYNAMIC) ---
    async def execute_dynamic_buy(self, side, token_id, price):
        if not self.client: return False
        
        # FAILSAFE: Prevent double execution within 60 seconds
        if time.time() - self.last_trade_ts < 60:
            self.log("WARNING: Trade blocked by 60s cooldown.")
            return None
        
        # --- DYNAMIC SIZING ---
        # Formula: Base 5% + (Price - 0.50)*0.56
        # Min Price: $0.40 (filtered before calling)
        # Cap: 33% of Capital
        
        wager_pct = 0.05 + max(0, (price - 0.50)) * 0.56
        wager_pct = min(0.33, wager_pct)
        
        usd_amount = self.risk_capital * wager_pct
        usd_amount = round(usd_amount, 2)
        
        shares = float(usd_amount) / price
        shares = round(shares, 2)
        
        self.log(f"DYNAMIC SIZE: {wager_pct:.1%} of ${self.risk_capital} -> ${usd_amount} (~{shares} shares)")
        
        limit_price = 0.99
        
        try:
            order_args = OrderArgs(
                price=limit_price,
                size=shares,
                side="BUY",
                token_id=token_id
            )
            
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
                    "cost": usd_amount, 
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
        print(f"--- LIVE *DYNAMIC* TRADING BOT ---")
        
        # --- Startup Config ---
        print("\n--- CONFIGURATION ---")
        
        # 0. Risk Capital
        ans_cap = input(f"0. Enter Risk Capital (Default $50.00): ").strip()
        if ans_cap:
            try: self.risk_capital = float(ans_cap)
            except: pass
        print(f"   >>> Risk Capital Set to: ${self.risk_capital:.2f}")

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
        
        print("Calibrating Price Offset...")
        await self.fetch_spot_price()
        print(f"Offset: {self.btc_offset:.2f}")
        
        while self.is_running:
            try:
                # Window Calc
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
                    self.market_url = url
                    self.log(f"Monitoring: {self.market_url}")
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
                    
                # Fetch Data
                await self.fetch_market_data()
                await self.fetch_spot_price() 
                
                # Strategy Logic
                drift_pct = 0.0
                if self.market_data["open_price"] > 0:
                     drift_pct = abs(self.market_data["btc_price"] - self.market_data["open_price"]) / self.market_data["open_price"]
                
                elapsed_mins = (time.time() - ts_start) / 60.0
                
                check_t6 = 5.9 <= elapsed_mins <= 6.1
                check_t9 = 8.9 <= elapsed_mins <= 9.1
                
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
                                 self.btc_offset = 0.0
                                 self.last_offset_update = 0
                                 self.strategy_triggered = True
                                 await self.fetch_spot_price()
                                 continue
                             
                             if price < 0.55:
                                 self.log(f"SKIPPED: {side} signal valid, but Price {price:.2f} too low/risky.")
                                 self.strategy_triggered = True
                                 continue

                             self.log(f"SIGNAL: {side} @ {price:.2f} (Drift {drift_pct:.4%})")
                             
                             # Conf Logic
                             should_execute = False
                             if self.manual_confirm:
                                 # Calculate potential size for display
                                 wager_pct = 0.05 + max(0, (price - 0.50)) * 0.56
                                 wager_pct = min(0.33, wager_pct)
                                 usd_est = self.risk_capital * wager_pct
                                 
                                 print(f"\n>>> CONFIRM DYNAMIC BUY: {side} @ {price:.2f} (Size: ${usd_est:.2f} / {wager_pct:.1%})?")
                                 print(">>> TYPE 'YES' TO EXECUTE")
                                 print('\a') 
                                 confirm = input(">>> ").strip().lower()
                                 if confirm == 'yes': should_execute = True
                                 else:
                                     self.log("Trade CANCELLED.")
                                     self.strategy_triggered = True 
                             else:
                                 self.log("AUTO-EXECUTING Signal...")
                                 should_execute = True
                             
                             if should_execute:
                                 self.strategy_triggered = True
                                 res = await self.execute_dynamic_buy(side, token_id, price)
                                 if res:
                                     self.active_trade = res
                                     # AUTO-EXIT
                                     await self.place_exit_order(res["token_id"], res["shares"])

                    else:
                         print_status(f"No Signal: Drift {drift_pct:.4%} low.")
                         await asyncio.sleep(5) 

                # Display Logic
                targets = [3.0, 6.0, 9.0, 15.0]
                next_target = 15.0
                mode = "NEXT BOUNDARY"
                for t in targets:
                    if elapsed_mins < t:
                        next_target = t
                        if t == 6.0 or t == 9.0: mode = f"CHECKPOINT (T+{int(t)}m)"
                        elif t == 15.0: mode = "NEXT ROUND (Market Close)"
                        else: mode = f"HEARTBEAT (T+{int(t)}m)"
                        break
                
                sleep_duration = (next_target * 60) - (elapsed_mins * 60)
                if self.active_trade:
                    mode = "NEXT ROUND (Market Close)"
                    sleep_duration = (15.0 * 60) - (elapsed_mins * 60) 
                
                trade_str = f"ACTIVE ({self.active_trade['side']})" if self.active_trade else "None"
                print_status(f"BTC: {self.market_data['btc_price']:,.1f} | OPEN: {self.market_data['open_price']:,.1f} | UP: {self.market_data['up_price']:.2f} DN: {self.market_data['down_price']:.2f} | Trade: {trade_str} | Drift: {drift_pct:.4%}")
                
                if sleep_duration > 5:
                    print(f"Waiting {int(sleep_duration)}s until {mode}...")
                    remaining = sleep_duration
                    while remaining > 0:
                        step = min(30, remaining)
                        await asyncio.sleep(step)
                        remaining -= step
                        
                        if remaining > 0:
                            await self.fetch_spot_price()
                            await self.fetch_market_data()
                            t_str = f"ACTIVE ({self.active_trade['side']})" if self.active_trade else "None"
                            d_pct = 0.0
                            if self.market_data["open_price"] > 0:
                                d_pct = abs(self.market_data["btc_price"] - self.market_data["open_price"]) / self.market_data["open_price"]
                            print_status(f"[HEARTBEAT] BTC: {self.market_data['btc_price']:,.1f} | UP: {self.market_data['up_price']:.2f} DN: {self.market_data['down_price']:.2f} | Drift: {d_pct:.4%} | Remain: {int(remaining)}s")
                else:
                    await asyncio.sleep(5)

            except KeyboardInterrupt: break
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        trader = LiveTraderDynamic()
        asyncio.run(trader.run())
    except KeyboardInterrupt: pass
