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
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams

# Load .env
load_dotenv()

# Environment Variables
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"

# --- CLI Helpers ---
def print_status(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")

class ManualBuyerV2:
    def __init__(self, use_proxy=True):
        self.session = requests.Session()
        self.client = None
        self.use_proxy = use_proxy
        self.market_data = {
            "up_id": None, "down_id": None, 
            "up_price": 0.0, "down_price": 0.0,
            "btc_price": 0.0, 
            "start_ts": 0
        }
        self.market_url = ""
        self._init_client()

    def _init_client(self):
        if not PRIVATE_KEY:
            print_status("CRITICAL: No PRIVATE_KEY found in .env!")
            sys.exit(1)
            
        try:
            # COPYING LOGIC FROM bot_trend_t9_LIVE.py
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
            
            # --- Check Balance (Extra safety, matching bot logic style) ---
            try:
                params = BalanceAllowanceParams(asset_type="COLLATERAL")
                bal_resp = self.client.get_balance_allowance(params)
                balance = float(bal_resp.get('balance', 0)) / 10**6 
                print_status(f"Balance: ${balance:.2f} (USDC)")
            except: pass
            
        except Exception as e:
            print_status(f"CRITICAL: Client Init Error: {e}")
            sys.exit(1)

    def log(self, msg):
        print_status(msg)

    async def fetch_current_market(self):
        # 1. Window Calc (Matching bot logic)
        now = datetime.now(timezone.utc)
        minutes = now.minute
        floor = (minutes // 15) * 15
        start_dt = now.replace(minute=floor, second=0, microsecond=0)
        ts_start = int(start_dt.timestamp())
        self.market_url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"
        self.market_data["start_ts"] = ts_start
        
        elapsed = int(time.time() - ts_start)
        remaining = 900 - elapsed
        self.log(f"Scanning Window: {start_dt.strftime('%H:%M')} (T-{remaining}s remaining)")

        # 2. Metadata (Matching bot logic)
        slug = self.market_url.split("/")[-1]
        url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
        resp = await asyncio.to_thread(self.session.get, url)
        
        if resp.status_code == 200:
            data = resp.json()
            if "clobTokenIds" in data:
                ids = json.loads(data["clobTokenIds"])
                outcomes = json.loads(data["outcomes"])
                
                up_idx, down_idx = 0, 1
                for i, name in enumerate(outcomes):
                    if "Up" in name or "Yes" in name: up_idx = i
                    elif "Down" in name or "No" in name: down_idx = i
                
                self.market_data["up_id"] = ids[up_idx]
                self.market_data["down_id"] = ids[down_idx]

        # 3. Prices (Matching bot logic)
        clob_url = "https://clob.polymarket.com/price"
        if self.market_data["up_id"]:
            p1 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["up_id"], "side": "buy"})
            p2 = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": self.market_data["down_id"], "side": "buy"})
            if p1.status_code == 200: self.market_data["up_price"] = float(p1.json().get("price", 0))
            if p2.status_code == 200: self.market_data["down_price"] = float(p2.json().get("price", 0))

        self.log(f"UP: {self.market_data['up_price']:.3f} | DOWN: {self.market_data['down_price']:.3f}")

    # --- EXECUTION LOGIC (EXACT COPY FROM bot_trend_t9_LIVE.py) ---
    async def execute_market_buy(self, side, token_id, usd_amount):
        if not self.client: return False
        
        # Get approx price to calculate shares
        price = self.market_data["up_price"] if side == "UP" else self.market_data["down_price"]
        if price <= 0: price = 0.50 # Safety fallback
        
        # Cap price at 0.99 to execute immediately
        limit_price = 0.99
              
        # Shares = USD / Price (This is an approximation)
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
            # Sync call in thread (EXACT SYNTAX FROM BOT)
            def _post():
                signed = self.client.create_order(order_args)
                return self.client.post_order(signed)
            
            resp = await asyncio.to_thread(_post)
            print(f"API Response: {resp}")
            
            if resp and (resp.get("success") or resp.get("orderID")):
                oid = resp.get("orderID") or "UNKNOWN"
                self.log(f"SUCCESS: Order Placed! ID: {oid}")
                return True
            else:
                 err = resp.get("errorMsg") if resp else "Unknown"
                 self.log(f"FAILURE: Order Failed: {err}")
                 return False
                 
        except Exception as e:
            self.log(f"EXCEPTION: Trade Error: {e}")
            return False

    async def run_manual(self):
        await self.fetch_current_market()
        print("\n--- MANUAL BUY v2 (Exact Syntax) ---")
        
        side_input = input("Enter Side (UP / DOWN) [or 'q' to quit]: ").strip().upper()
        if side_input in ['Q', 'QUIT']: return
        
        if side_input not in ["UP", "DOWN"]:
            print("Invalid side.")
            return

        amount = input("Enter Amount ($): ").strip()
        if not amount: return
        
        token_id = self.market_data["up_id"] if side_input == "UP" else self.market_data["down_id"]
        
        # Execute using the exact copied method
        await self.execute_market_buy(side_input, token_id, float(amount))

if __name__ == "__main__":
    t = ManualBuyerV2()
    try:
        asyncio.run(t.run_manual())
    except KeyboardInterrupt:
        print("\nExited.")
