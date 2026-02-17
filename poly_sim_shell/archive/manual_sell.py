import asyncio
import os
import sys
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams

# Monkey-patch requests.Session to default to Chrome UA (Enhanced)
original_init = requests.Session.__init__
def new_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://polymarket.com/",
        "Origin": "https://polymarket.com",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site"
    })
requests.Session.__init__ = new_init

# Load .env
load_dotenv()

# --- CONSTANTS ---
CHAIN_ID = 137
HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PROXY_ADDRESS = os.getenv("PROXY_ADDRESS")

class ManualSeller:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.client = None
        self.market_data = {
            "up_id": None, "down_id": None, 
            "up_price": 0.0, "down_price": 0.0,
            "btc_price": 0.0, "open_price": 0.0,
            "start_ts": 0
        }
        self.market_url = ""

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def init_client(self):
        if not PRIVATE_KEY:
            self.log("CRITICAL: No PRIVATE_KEY in .env!")
            sys.exit(1)
        try:
            key_acct = Account.from_key(PRIVATE_KEY)
            funder = PROXY_ADDRESS if PROXY_ADDRESS else key_acct.address
            
            self.client = ClobClient(
                host=HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID, 
                signature_type=1 if PROXY_ADDRESS else 0, funder=funder
            )
            creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(creds)
            self.log(f"Connected to Polymarket (Funder: {funder})")

            # --- DIAGNOSTICS: Check Balance & Allowance ---
            try:
                params = BalanceAllowanceParams(asset_type="COLLATERAL")
                bal_resp = self.client.get_balance_allowance(params)
                
                balance = float(bal_resp.get('balance', 0)) / 10**6 
                allowance = float(bal_resp.get('allowance', 0)) / 10**6
                
                self.log(f"--- ACCOUNT DIAGNOSTICS ---")
                self.log(f"Address:   {funder}")
                self.log(f"Balance:   ${balance:.2f} (USDC)")
                self.log(f"Allowance: ${allowance:.2f}")

            except Exception as e:
                self.log(f"Could not fetch balance: {e}")

        except Exception as e:
            self.log(f"Client Init Error: {e}")
            sys.exit(1)

    async def fetch_current_market(self):
        # 1. Calculate Window
        now_dt = datetime.now(timezone.utc)
        minutes = now_dt.minute
        floor = (minutes // 15) * 15
        start_dt = now_dt.replace(minute=floor, second=0, microsecond=0)
        ts_start = int(start_dt.timestamp())
        self.market_url = f"https://polymarket.com/event/btc-updown-15m-{ts_start}"
        self.market_data["start_ts"] = ts_start
        
        elapsed = int(time.time() - ts_start)
        remaining = 900 - elapsed
        self.log(f"Scanning Window: {start_dt.strftime('%H:%M')} (T-{remaining}s remaining)")
        
        # 2. Get Metadata
        slug = self.market_url.split("/")[-1]
        url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
        resp = await asyncio.to_thread(self.session.get, url)
        
        if resp.status_code != 200:
            self.log("Error fetching market metadata.")
            return

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
            
        # 3. Get Prices
        clob_url = "https://clob.polymarket.com/price"
        for side, token_id in [("UP", self.market_data["up_id"]), ("DOWN", self.market_data["down_id"])]:
            p = await asyncio.to_thread(self.session.get, clob_url, params={"token_id": token_id, "side": "buy"})
            if p.status_code == 200:
                price = float(p.json().get("price", 0))
                if side == "UP": self.market_data["up_price"] = price
                else: self.market_data["down_price"] = price

        self.log(f"UP: {self.market_data['up_price']:.3f} | DOWN: {self.market_data['down_price']:.3f}")

    async def run(self):
        self.init_client()
        await self.fetch_current_market()
        
        print("\n--- MANUAL SELL ENTRY (CLOSE POSITION) ---")
        try:
            side_input = input("Enter Side to SELL (UP / DOWN) [or 'q' to quit]: ").strip().upper()
            if side_input in ['Q', 'QUIT', 'EXIT']:
                print("Exiting cleanly.")
                return

            if side_input not in ["UP", "DOWN"]:
                print("Invalid side. Exiting.")
                return
            
            side = side_input

            # 1. Ask for Share Amount
            amount_str = input("Enter Amount (Shares): ").strip()
            if amount_str.lower() in ['q', 'quit']: return
            shares = float(amount_str)

            # 2. Ask for Limit Price
            # Default to current market price if they just hit enter? 
            # Or force them to set it. User said "i get to specify sell price".
            price_str = input(f"Enter Limit Price ($) [Current: {self.market_data['up_price' if side=='UP' else 'down_price']:.3f}]: ").strip()
            if price_str.lower() in ['q', 'quit']: return
            
            if not price_str:
                print("Price required. Exiting.")
                return
            
            limit_price = float(price_str)

            # Execute
            token_id = self.market_data["up_id"] if side == "UP" else self.market_data["down_id"]
            
            # Estimate Value
            est_value = shares * limit_price

            proceed = input(f"\n>>> SELL {shares} shares of {side} @ ${limit_price:.3f} (Est. Value: ${est_value:.2f})? [y/N]: ").lower()
            if proceed != 'y':
                print("Cancelled.")
                return

            self.log("Executing LIMIT SELL...")
            
            # LIMIT SELL ORDER
            order = OrderArgs(
                price=limit_price, size=shares, side="SELL", token_id=token_id
            )
            resp = await asyncio.to_thread(lambda: self.client.post_order(self.client.create_order(order)))
            
            if resp and (resp.get("success") or resp.get("orderID")):
                self.log(f"SUCCESS! Order ID: {resp.get('orderID')}")
            else:
                self.log(f"FAILED: {resp.get('errorMsg')}")

        except KeyboardInterrupt:
            print("\n\nCancelled by user (Ctrl+C). Exiting cleanly.")
            return
        except Exception as e:
            self.log(f"EXCEPTION: {e}")

if __name__ == "__main__":
    t = ManualSeller()
    try:
        asyncio.run(t.run())
    except KeyboardInterrupt:
        print("\nExited.")
