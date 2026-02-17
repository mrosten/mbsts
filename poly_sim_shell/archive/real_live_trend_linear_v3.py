"""
REAL LIVE BOT v3 - Data-Driven Edition
---------------------------------------
Based on Sim v3 Logic + Real v2 Infrastructure.
WARNING: TRADES REAL MONEY.
"""

import os
import sys
import time
import json
import asyncio
import requests
import csv
from datetime import datetime, timezone
from dotenv import load_dotenv

# Web3 / Clob
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams, PartialCreateOrderOptions

# Monkey-patch requests
original_init = requests.Session.__init__
def new_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
    })
requests.Session.__init__ = new_init

load_dotenv()

# --- v3 Configuration (Data-Driven) ---
DRIFT_THRESHOLD = 0.0004
MAX_COST = 15.0      # Hard cap
MIN_COST = 5.0       # Minimum trade
BAD_HOURS_UTC = {5, 8, 11, 16}
REDUCED_HOURS_UTC = {4, 13}
MAX_CONSECUTIVE_RISES = 4

HOST = "https://clob.polymarket.com"
CHAIN_ID = 137
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")

def print_status(msg, log_to_file=False, log_file=None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    if log_to_file and log_file:
        with open(log_file, "a", encoding='utf-8') as f:
            f.write(line + "\n")

class RealLiveLinearBotV3:
    def __init__(self, use_bb_sizing=True):
        self.session = requests.Session()
        
        # State
        self.is_running = True
        self.market_url = ""
        self.active_trade = None
        self.strategy_triggered = False
        self.checkpoints = {} # {second: price}
        
        # Real Account State
        self.client = None
        self.real_balance_usdc = 0.0
        self.funder_address = ""
        
        # Data
        self.btc_offset = -86.0
        self.auto_offset = True
        self.market_data = {
            "up_id": None, "down_id": None, 
            "up_price": 0.0, "down_price": 0.0,
            "btc_price": 0.0, "open_price": 0.0,
            "start_ts": 0
        }
        self.use_bb_sizing = use_bb_sizing
        self.reserved_excess = 0.0
        self._last_sizing_notes = []
        
        # v3 Stats
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.session_pnl = 0.0
        self.total_wins = 0
        self.total_losses = 0
        self.window_count = 0
        self.loss_tracker_file = "loss_tracker_v3.json"
        
        # Logging
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = f"REAL_live_v3_log_{timestamp_str}.txt"
        self.csv_file = None
        self.csv_writer = None
        self.csv_filename = f"REAL_live_v3_detailed_{timestamp_str}.csv"
        
        self.load_loss_state()
        self.init_client()

    def log(self, msg):
        print_status(msg, log_to_file=True, log_file=self.log_file)

    def load_loss_state(self):
        try:
            if os.path.exists(self.loss_tracker_file):
                with open(self.loss_tracker_file, "r") as f:
                    data = json.load(f)
                    self.consecutive_losses = data.get("losses", 0)
                    self.log(f"Loss State Loaded: {self.consecutive_losses} consecutive losses.")
        except: pass

    def save_loss_state(self):
        try:
            with open(self.loss_tracker_file, "w") as f:
                json.dump({"losses": self.consecutive_losses}, f)
        except: pass

    def init_client(self):
        if not PRIVATE_KEY:
            self.log("CRITICAL: No PRIVATE_KEY in .env!")
            sys.exit(1)
        try:
            key_acct = Account.from_key(PRIVATE_KEY)
            # Default to PROXY if available (signature_type=1)
            # NOTE: If user has invalid proxy keys, this will fail at trade time.
            self.funder_address = PROXY_ADDRESS if PROXY_ADDRESS else key_acct.address
            sig_type = 1 if PROXY_ADDRESS else 0
            
            self.client = ClobClient(
                host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, 
                signature_type=sig_type, funder=self.funder_address
            )
            creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(creds)
            self.log(f"Connected to Polymarket (Funder: {self.funder_address}, SigType: {sig_type})")
        except Exception as e:
            self.log(f"Client Init Error: {e}")
            sys.exit(1)

    def update_real_balance(self):
        try:
            params = BalanceAllowanceParams(asset_type="COLLATERAL")
            bal_resp = self.client.get_balance_allowance(params)
            self.real_balance_usdc = float(bal_resp.get('balance', 0)) / 10**6
        except Exception as e:
            self.log(f"Error fetching balance: {e}")

    # --- Data Fetching ---
    async def fetch_spot_price(self):
        # Simplistic fetcher for now (Binance/Coinbase)
        price = 0.0
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            resp = await asyncio.to_thread(self.session.get, url, timeout=2.0)
            data = resp.json()
            if "price" in data: price = float(data["price"])
        except: pass
        
        if price == 0:
            try:
                url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
                resp = await asyncio.to_thread(self.session.get, url, timeout=3.0)
                price = float(resp.json()['data']['amount'])
            except: pass

        if price > 0:
            # Apply fixed offset (or calibrated)
            self.market_data["btc_price"] = price + self.btc_offset
            
            # Cache Open
            if self.market_data["open_price"] == 0 and self.market_data["start_ts"] > 0:
                if (time.time() - self.market_data["start_ts"]) < 300:
                     self.market_data["open_price"] = self.market_data["btc_price"]
                     self.log(f"OPEN PRICE SET: {self.market_data['open_price']:,.2f}")

    async def fetch_market_data(self):
        # 1. IDs (Gamma)
        if not self.market_data["up_id"] and self.market_url:
            try:
                slug = self.market_url.split("/")[-1].split("?")[0]
                url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
                resp = await asyncio.to_thread(self.session.get, url, timeout=2.0)
                if resp.json() and "clobTokenIds" in resp.json():
                    ids = json.loads(resp.json()["clobTokenIds"])
                    self.market_data["up_id"] = ids[0]
                    self.market_data["down_id"] = ids[1]
            except: pass

        # 2. Prices (CLOB /price)
        if self.market_data["up_id"]:
            try:
                url = f"{HOST}/price"
                p1 = await asyncio.to_thread(self.session.get, url, params={"token_id": self.market_data["up_id"], "side": "buy"})
                p2 = await asyncio.to_thread(self.session.get, url, params={"token_id": self.market_data["down_id"], "side": "buy"})
                if p1.status_code == 200: self.market_data["up_price"] = float(p1.json().get("price", 0))
                if p2.status_code == 200: self.market_data["down_price"] = float(p2.json().get("price", 0))
            except: pass

    # --- v3 Calculation Logic ---
    def calculate_bollinger_metrics(self):
        BB_PERIOD = 36
        default = {"position": 0.5, "size_multiplier": 1.0, "at_edge": False}
        if len(self.checkpoints) < BB_PERIOD: return default
        
        prices = [self.checkpoints[t] for t in sorted(self.checkpoints.keys())[-BB_PERIOD:]]
        sma = sum(prices) / len(prices)
        std = (sum((p - sma)**2 for p in prices) / len(prices)) ** 0.5
        upper = sma + 2*std
        lower = sma - 2*std
        
        width = upper - lower
        pos = 0.5
        if width > 0:
            pos = (prices[-1] - lower) / width
            pos = max(0.0, min(1.0, pos))
            
        mult = 1.5 - (abs(pos - 0.5) * 2.0)
        mult = max(0.5, min(1.5, mult))
        
        return {
            "position": pos, "size_multiplier": mult,
            "upper": upper, "lower": lower, "width": width, "at_edge": False
        }

    def calculate_trade_cost(self, budget_pct, bb_multiplier):
        # 1. Base
        balance = max(0.0, self.real_balance_usdc - self.reserved_excess)
        base_cost = balance * budget_pct
        notes = []
        
        # 2. BB
        if self.use_bb_sizing:
            cost = base_cost * bb_multiplier
            if abs(bb_multiplier - 1.0) > 0.05: notes.append(f"BB {bb_multiplier:.2f}x")
        else:
            cost = base_cost
            
        # 3. Hard Cap (v3)
        if cost > MAX_COST:
            notes.append(f"capped ${cost:.0f}->${MAX_COST:.0f}")
            cost = MAX_COST
            
        # 4. Time of Day (v3)
        hour = datetime.now(timezone.utc).hour
        if hour in BAD_HOURS_UTC:
            cost *= 0.60
            notes.append(f"bad-hour({hour}h)")
        elif hour in REDUCED_HOURS_UTC:
            cost *= 0.80
            notes.append(f"caution-hour({hour}h)")
            
        # 5. Streak (v3)
        if self.consecutive_losses >= 2:
            cost *= 0.70
            notes.append(f"streak({self.consecutive_losses}L)")
            
        cost = max(MIN_COST, cost)
        cost = min(cost, balance) # Ensure we have funds
        
        self._last_sizing_notes = notes
        return cost

    # --- Strategy Loop ---
    async def run(self):
        print("--- REAL LIVE BOT v3 (Data-Driven) ---")
        try:
             ans = input(f"Starting Bankroll (Enter for All, or amount): ").strip()
             if ans:
                 amt = float(ans)
                 self.update_real_balance()
                 if amt < self.real_balance_usdc:
                     self.reserved_excess = self.real_balance_usdc - amt
                     print(f"   Reserved Excess: ${self.reserved_excess:.2f}")
        except: pass
        
        self.update_real_balance()
        print(f"Wallet: ${self.real_balance_usdc:.2f}")
        
        self.init_csv_logging()

        while self.is_running:
            try:
                now = datetime.now(timezone.utc)
                min15 = (now.minute // 15) * 15
                start_dt = now.replace(minute=min15, second=0, microsecond=0)
                ts_start = int(start_dt.timestamp())
                url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"

                if url != self.market_url:
                    self.market_url = url
                    self.window_count += 1
                    self.market_data = {
                        "up_id": None, "down_id": None, 
                        "up_price": 0.0, "down_price": 0.0,
                        "btc_price": self.market_data["btc_price"], 
                        "open_price": 0.0, "start_ts": ts_start
                    }
                    self.checkpoints = {}
                    self.active_trade = None
                    self.strategy_triggered = False
                    self.update_real_balance()
                    
                    hour = start_dt.hour
                    print(f"\n[{start_dt.strftime('%H:%M')} UTC] WINDOW #{self.window_count} (Hour {hour})")
                    self.log(f"NEW WINDOW #{self.window_count}: {start_dt.strftime('%H:%M')} UTC | Bal: ${self.real_balance_usdc:.2f}")

                # Update Data
                await self.fetch_spot_price()
                await self.fetch_market_data()
                
                elapsed = int(time.time() - ts_start)
                self.print_status_line(elapsed)
                
                if self.market_data["open_price"] > 0:
                    await self.process_strategy(elapsed)

                await asyncio.sleep(5)
            except KeyboardInterrupt: break
            except Exception as e:
                self.log(f"Loop Error: {e}")
                await asyncio.sleep(5)

    def print_status_line(self, elapsed):
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        drift = abs(btc - op) / op if op > 0 else 0
        rem = 900 - elapsed
        trade = "ACTIVE" if self.active_trade else "SCAN"
        print(f"\r[T-{rem}s] BTC:{btc:,.0f} OP:{op:,.0f} | {trade} | Bal:${self.real_balance_usdc:.2f}   ", end="", flush=True)

    async def process_strategy(self, elapsed):
        if self.strategy_triggered: return
        
        btc = self.market_data["btc_price"]
        op = self.market_data["open_price"]
        leader_side = "UP" if btc > op else "DOWN"
        leader_price = self.market_data["up_price"] if leader_side == "UP" else self.market_data["down_price"]
        drift = abs(btc - op) / op

        # Checkpoints
        if 300 <= elapsed <= 540:
             if elapsed not in self.checkpoints:
                 self.checkpoints[elapsed] = leader_price
                 self.log_checkpoint(elapsed, leader_side, leader_price, "MONITOR")

        # --- SIGNAL 1: HIGH CONFIDENCE (Rising 88-92) ---
        if 300 <= elapsed <= 540:
             if 0.88 <= leader_price < 0.93 and drift > DRIFT_THRESHOLD:
                if len(self.checkpoints) >= 2:
                    times = sorted(self.checkpoints.keys())
                    if self.checkpoints[times[-1]] > self.checkpoints[times[-2]]:
                        # TRIGGER
                        bb = self.calculate_bollinger_metrics()
                        cost = self.calculate_trade_cost(0.05, bb["size_multiplier"])
                        await self.execute_real_trade("HIGH-CONF", leader_side, leader_price, cost)
                        return

        # --- SIGNAL 2: STRONG UPTREND ---
        if 300 <= elapsed <= 540:
             times = sorted(self.checkpoints.keys())
             if len(times) >= 3:
                 recent = [self.checkpoints[t] for t in times if elapsed - t <= 90]
                 if len(recent) >= 3:
                     # Momentum
                     mom = recent[-1] - recent[0]
                     
                     # Consistency
                     consec = 0
                     max_consec = 0
                     for i in range(1, len(recent)):
                         if recent[i] > recent[i-1]:
                             consec += 1
                             max_consec = max(max_consec, consec)
                         else: consec = 0
                         
                     # Exhaustion
                     if max_consec >= MAX_CONSECUTIVE_RISES + 1:
                         return # Skip

                     # Sweet Spot
                     in_sweet_spot = leader_price < 0.72
                     budget_pct = 0.20 if in_sweet_spot else 0.12
                     
                     if (mom >= 0.10 and max_consec >= 2 and drift > DRIFT_THRESHOLD 
                         and leader_price < 0.85):
                         
                         bb = self.calculate_bollinger_metrics()
                         cost = self.calculate_trade_cost(budget_pct, bb["size_multiplier"])
                         await self.execute_real_trade("UPTREND", leader_side, leader_price, cost)
                         return

    async def execute_real_trade(self, type_name, side, price, cost):
        self.log(f"EXECUTING {type_name}: {side} @ {price:.2f} (Cost ${cost:.2f})")
        token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
        
        shares = round(cost / price, 2)
        # Limit Price: Cap at 0.99 or Current+0.05
        limit_price = min(0.99, price + 0.05)
        
        # ATTEMPT 1: neg_risk=True
        resp = None
        try:
            order = OrderArgs(price=limit_price, size=shares, side="BUY", token_id=token_id)
            try:
                options = PartialCreateOrderOptions(neg_risk=True)
                signed = self.client.create_order(order, options)
                resp = await asyncio.to_thread(lambda: self.client.post_order(signed))
            except: 
                # ATTEMPT 2: neg_risk=False
                try:
                    options = PartialCreateOrderOptions(neg_risk=False)
                    signed = self.client.create_order(order, options)
                    resp = await asyncio.to_thread(lambda: self.client.post_order(signed))
                except: pass

            if resp and resp.get("orderID"):
                self.log(f"BUY SUCCESS! OrderID: {resp.get('orderID')}")
                self.active_trade = {"side": side, "cost": cost, "shares": shares}
                self.strategy_triggered = True
                
                self.log("Waiting for shares...")
                await asyncio.sleep(5) 
                
                # Auto-Sell
                b_params = BalanceAllowanceParams(asset_type="CONDITIONAL", token_id=token_id)
                bal = await asyncio.to_thread(lambda: self.client.get_balance_allowance(b_params))
                shares_owned = float(bal.get("balance", "0")) / 10**6
                
                if shares_owned > 0.1:
                    self.log(f"Placing TP Sell for {shares_owned} shares...")
                    s_order = OrderArgs(price=0.99, size=shares_owned, side="SELL", token_id=token_id)
                    try:
                        # SELL usually uses neg_risk=False or auto? For SELL, CLOB just needs to know tokenID.
                        # But for consistency, let's just try create_order defaults.
                        s_signed = self.client.create_order(s_order)
                        s_resp = await asyncio.to_thread(lambda: self.client.post_order(s_signed))
                        self.log(f"TP Placed: {s_resp}")
                    except Exception as e:
                        self.log(f"TP Error: {e}")
            else:
                self.log(f"BUY FAILED: {resp}")
        except Exception as e:
            self.log(f"Trade Exception: {e}")

    def init_csv_logging(self):
        self.csv_file = open(self.csv_filename, 'w', newline='')
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=['timestamp', 'elapsed', 'action', 'price', 'balance'])
        self.csv_writer.writeheader()

    def log_checkpoint(self, elapsed, side, price, action):
        if self.csv_writer:
            self.csv_writer.writerow({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'elapsed': elapsed,
                'action': action,
                'price': price,
                'balance': self.real_balance_usdc
            })
            self.csv_file.flush()

if __name__ == "__main__":
    bot = RealLiveLinearBotV3()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\nStopped.")
