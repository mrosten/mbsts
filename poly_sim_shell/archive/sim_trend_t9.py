"""
Broken - Does not have proper Open Price.
This file checks live data from Polymarket and Binance, and does simulated trades in real time. 

Simulator: Trend Strategy (T+9)

Backtester for the classic T+9 Trend strategy.
- Uses 3-minute interval data (Open/Close).
- Checks drift at checkpoints (6m, 9m) independent of volatility.
- Tracks PnL for flat betting.
"""
import requests
import time
import json
import asyncio
import sys
from datetime import datetime, timezone, timedelta
import os

STATE_FILE = "sim_state.json"
LOG_FILE = "sim_log.txt"

# --- CLI Helpers ---
def print_status(msg, log_to_file=False):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    if log_to_file:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")

# --- Core Logic ---
class CLISimulation:
    def __init__(self, balance, resume=False):
        self.balance = float(balance)
        self.trade_size = 5.5
        
        # Offsets
        self.OFFSET_JERUSALEM = timedelta(hours=2)
        self.btc_offset = -86.0
        self.auto_offset = True
        self.last_offset_update = 0
        
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
        self.session = requests.Session()
        
        if resume:
            self.load_state()

    def log(self, msg):
        print_status(msg, log_to_file=True)

    def save_state(self):
        state = {
            "balance": self.balance,
            "btc_offset": self.btc_offset,
            "active_trade": self.active_trade,
            "market_url": self.market_url,
            "strategy_triggered": self.strategy_triggered
        }
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")

    def load_state(self):
        if not os.path.exists(STATE_FILE): return
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                self.balance = state.get("balance", self.balance)
                self.btc_offset = state.get("btc_offset", self.btc_offset)
                self.active_trade = state.get("active_trade", None)
                self.market_url = state.get("market_url", "")
                self.strategy_triggered = state.get("strategy_triggered", False)
                print_status(f"*** RESUMED STATE: Bal=${self.balance:.2f} | Offset={self.btc_offset} ***", log_to_file=True)
        except Exception as e:
            print(f"Error loading state: {e}")

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
                     if op > 0: self.market_data["open_price"] = op
                     elif (time.time() - self.market_data["start_ts"]) < 60:
                         self.market_data["open_price"] = price
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
                        if len(ids) >= 2:
                            self.market_data["up_id"] = ids[0]
                            self.market_data["down_id"] = ids[1]
            except: pass

        # Prices
        if self.market_data["up_id"]:
            try:
                clob_url = "https://clob.polymarket.com/price"
                p1 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["up_id"], "side": "buy"})
                p2 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["down_id"], "side": "buy"})
                
                r1, r2 = p1.json(), p2.json()
                if "price" in r1: self.market_data["up_price"] = float(r1["price"])
                if "price" in r2: self.market_data["down_price"] = float(r2["price"])
            except: pass

    # --- Main Loop ---
    async def run(self):
        print(f"--- PolySim CLI (Event Based) ---")
        print(f"Initial Balance: ${self.balance:.2f} | Trade Size: {self.trade_size}")
        print("Calibrating Price Offset...")
        await self.fetch_spot_price()
        print(f"Offset: {self.btc_offset:.2f}")

        while self.is_running:
            try:
                # 1. Sync Price First (Crucial for Settlement)
                await self.fetch_spot_price()

                # 2. Calculate Window & Time
                now = datetime.now(timezone.utc)
                minutes = now.minute
                floor = (minutes // 15) * 15
                start_dt = now.replace(minute=floor, second=0, microsecond=0)
                end_dt = start_dt + timedelta(minutes=15)
                
                ts_start = int(start_dt.timestamp())
                url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"
                
                # Check New Market (Resolution)
                if url != self.market_url:
                    # Resolve Previous Market
                    if self.market_url != "":
                         final_btc = self.market_data["btc_price"]
                         final_open = self.market_data["open_price"]
                         
                         if final_open > 0:
                             winner = "UP" if final_btc > final_open else "DOWN"
                             print(f"\n\n=== MARKET CLOSED ===")
                             print(f"Final BTC: {final_btc:,.2f} | Open: {final_open:,.2f}")
                             self.log(f"MARKET CLOSED. Result: {winner} wins. Final BTC: {final_btc}")
                             
                             if self.active_trade:
                                 side = self.active_trade["side"]
                                 shares = self.active_trade["shares"] # This is just trade_size (dollars) / price? No, code says shares = trade_size. 
                                 # Wait, standard trade_size is usually $5.50. 
                                 # Logic check: `cost = price * self.trade_size` -> So `trade_size` is actually "Max Shares"?
                                 # Let's check `execute_trade`: `shares` key was stored as `self.trade_size`. 
                                 # And `cost` was `price * self.trade_size`.
                                 # So yes, `trade_size` = Number of Shares (e.g. 5.5 shares).
                                 
                                 if side == winner:
                                     payout = shares * 1.00
                                     profit = payout - self.active_trade["cost"]
                                     self.balance += payout
                                     self.log(f"TRADE WON ({side}). Payout: ${payout:.2f} (Profit: ${profit:.2f})")
                                 else:
                                     self.log(f"TRADE LOST ({side}). Loss: -${self.active_trade['cost']:.2f}")
                             else:
                                 print("No active trade.")
                                 
                             print(f"New Balance: ${self.balance:.2f}")
                             print("=====================\n")
                             self.save_state()

                    self.market_url = url
                    btc = self.market_data["btc_price"]
                    self.market_data = {
                        "up_id": None, "down_id": None, 
                        "up_price": 0.0, "down_price": 0.0,
                        "btc_price": btc, 
                        "open_price": 0.0,
                        "start_ts": ts_start, "end_ts": end_dt.timestamp()
                    }
                    self.strategy_triggered = False
                    self.active_trade = None # Reset trade on new window
                    
                # 3. Fetch Data (Just Market Data now, Spot already done)
                await self.fetch_market_data()
                
                # 3. Analyze & Decide Next Sleep
                elapsed_mins = (time.time() - ts_start) / 60.0
                
                # Strategy Execution Logic (Moved BEFORE Plan for correct status)
                drift_pct = 0.0
                if self.market_data["open_price"] > 0:
                     drift_pct = abs(self.market_data["btc_price"] - self.market_data["open_price"]) / self.market_data["open_price"]
                
                check_t6 = 5.9 <= elapsed_mins <= 6.1
                check_t9 = 8.9 <= elapsed_mins <= 9.1
                
                if (check_t6 or check_t9) and not self.strategy_triggered and not self.active_trade:
                    # Note: We don't set 'plan' string here anymore, we let the Plan block below handle it.
                    # But we can print "CHECKING SIGNAL..." if we want immediate feedback?
                    # Actually, let's keep it silent unless it triggers, or just let 'Plan' status handle the waiting message.
                    if drift_pct > 0.0004:
                         side = "UP" if self.market_data["btc_price"] > self.market_data["open_price"] else "DOWN"
                         price = self.market_data["up_price"] if side=="UP" else self.market_data["down_price"]
                         if price > 0:
                             cost = price * self.trade_size
                             self.balance -= cost
                             self.active_trade = {
                                 "side": side, 
                                 "price": price, 
                                 "shares": self.trade_size,
                                 "cost": cost
                             }
                             self.strategy_triggered = True
                             self.log(f"*** EXECUTE: BUY {side} @ {price:.3f} (Drift {drift_pct:.4%}) ***")
                             self.save_state()
                    else:
                         # Optional: Debug print for failures?
                         # print_status(f"NO TRADE: Drift {drift_pct:.4%} too low.")
                         pass

                # Plan Determination
                plan = ""
                sleep_duration = 10 # Default fallback
                
                # Strategy Times: 6m and 9m
                t6_target = 6.0
                t9_target = 9.0
                close_target = 15.0
                
                mode = "WAIT"
                
                if self.active_trade and elapsed_mins < close_target:
                    mode = "NEXT ROUND (Market Close)"
                    sleep_duration = (close_target * 60) - (elapsed_mins * 60)
                elif elapsed_mins < t6_target:
                    mode = "CHECKPOINT (T+6m)"
                    sleep_duration = (t6_target * 60) - (elapsed_mins * 60)
                elif elapsed_mins < t9_target:
                    mode = "CHECKPOINT (T+9m)"
                    sleep_duration = (t9_target * 60) - (elapsed_mins * 60)
                elif elapsed_mins < close_target:
                    mode = "NEXT ROUND (Market Close)"
                    sleep_duration = (close_target * 60) - (elapsed_mins * 60)
                else:
                    mode = "NEXT ROUND"
                    sleep_duration = 60 # Wait for next window start

                
                # Print Status
                up = self.market_data["up_price"]
                down = self.market_data["down_price"]
                op = self.market_data["open_price"]
                
                trade_str = f"In Trade ({self.active_trade['side']})" if self.active_trade else "No Trade"
                
                print_status(f"BTC: {self.market_data['btc_price']:,.1f} | OPEN: {op:,.1f} | UP: {up:.2f} DN: {down:.2f} | BAL: ${self.balance:.2f}")
                print(f"Status: {trade_str} | Drift: {drift_pct:.3%} | Plan: Sleep {int(sleep_duration)}s until {mode}")
                print("----------------------------------------------------------------")
                
                # Sleep
                if sleep_duration > 0:
                    await asyncio.sleep(sleep_duration)
                else:
                    await asyncio.sleep(5) # Safety buffer

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        resume = False
        if os.path.exists(STATE_FILE):
             ans = input("Found saved state. Resume? [Y/n]: ").strip().lower()
             if ans == '' or ans == 'y':
                 resume = True
        
        b = 50.0
        if not resume:
            val = input("Enter Starting Balance [50]: ")
            b = float(val) if val.strip() else 50.0
            
        sim = CLISimulation(b, resume=resume)
        asyncio.run(sim.run())
    except KeyboardInterrupt: pass
